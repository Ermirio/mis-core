from datetime import datetime, timedelta
from django.utils import timezone
from .models import LinhaProducao, TurnoProducao, MetricaProducao, HistoricoSKU, CalendarioProducao
from .agregador import AgregadorDados

def calculate_projection(linha_id, produzido_realtime=None, formato_gramas=None):
    """
    Calcula projeção de produção para o turno atual da linha.
    Args:
        linha_id: ID da linha
        produzido_realtime: Produção atual em peças (opcional)
        formato_gramas: Peso da peça em gramas (opcional, para converter meta de KG para Unidades)
    """
    try:
        linha = LinhaProducao.objects.get(id=linha_id)
    except LinhaProducao.DoesNotExist:
        return None

    agregador = AgregadorDados()
    turno_atual = agregador.obter_turno_atual()
    
    if not turno_atual:
        return {
            "error": "Nenhum turno ativo no momento"
        }

    agora = timezone.now()
    inicio_turno, fim_turno = agregador.obter_intervalo_turno(turno_atual, agora)
    
    # Garantir que datas estejam no mesmo fuso horário de agora
    if timezone.is_aware(agora) and timezone.is_naive(inicio_turno):
        inicio_turno = timezone.make_aware(inicio_turno)
    if timezone.is_aware(agora) and timezone.is_naive(fim_turno):
        fim_turno = timezone.make_aware(fim_turno)

    # Se inicio_turno tem timezone, converter agora para o mesmo timezone para comparação correta
    if timezone.is_aware(inicio_turno):
        agora = agora.astimezone(inicio_turno.tzinfo)
    
    # Buscar métrica atual do turno
    metrica = MetricaProducao.objects.filter(
        linha=linha,
        periodo='TURNO',
        turno=turno_atual.nome,
        data_hora=inicio_turno
    ).first()

    # Usa valor real-time se fornecido, senão usa do banco
    if produzido_realtime is not None:
        produzido = produzido_realtime
    else:
        produzido = metrica.contagem_saida if metrica else 0
        
    velocidade_real = metrica.velocidade_real if metrica else 0
    
    # Calcular tempo restante
    if agora > fim_turno:
        tempo_restante_min = 0
    else:
        tempo_restante_min = (fim_turno - agora).total_seconds() / 60.0

    # Projeções
    # 1. Baseada na velocidade atual (Realista)
    projecao_realista = produzido + (velocidade_real * tempo_restante_min)
    
    # 2. Baseada na velocidade nominal/planejada (Otimista / Best Case)
    # Considera a velocidade planejada ajustada pela meta de OEE (Eficiência Planejada)
    velocidade_planejada = linha.velocidade_planejada
    fator_eficiencia = linha.meta_oee / 100.0 if linha.meta_oee else 0.85
    velocidade_otimista = velocidade_planejada * fator_eficiencia
    
    projecao_otimista = produzido + (velocidade_otimista * tempo_restante_min)
    projecao_otimista = max(produzido, projecao_otimista)

    # Obter Meta
    # Prioridade 1: Calendário de Produção (Meta do dia/turno específico)
    meta = 0
    op = "N/A"
    
    calendario = CalendarioProducao.objects.filter(
        linha=linha,
        data=agora.date(),
        turno=turno_atual
    ).first()
    
    if calendario:
        meta = calendario.meta_producao_turno
        
    # SE houver formato, assume que a meta cadastrada está em KG e converte para Unidades
    # Isso alinha o Admin (55000 kg) com o Dashboard (55 Tons)
    if meta > 0 and formato_gramas and formato_gramas > 0:
        peso_peca_kg = formato_gramas / 1000.0
        meta = int(round(meta / peso_peca_kg))
    
    # Prioridade 2: Histórico SKU (Meta da OP)
    if meta == 0:
        historico_sku = agregador.obter_sku_ativo(linha, agora)
        if historico_sku:
            # Se não tiver meta do calendário, usa da OP
            meta = historico_sku.meta_producao
            op = historico_sku.ordem_producao
    
    # Prioridade 3: Default da Linha
    if meta == 0:
        meta = linha.meta_producao_turno

    # Se ainda for 0, calcula baseado na capacidade da linha (Velocidade * OEE * Tempo Turno)
    tempo_total_min = (fim_turno - inicio_turno).total_seconds() / 60.0
    if meta == 0 and velocidade_planejada > 0:
        meta = int(tempo_total_min * velocidade_otimista)

    # Calcular Meta Atual (Esperado para o momento)
    # Fórmula: Tempo Decorrido * Velocidade Planejada * (Meta OEE / 100)
    # Isso garante que o esperado reflita a eficiência planejada
    tempo_decorrido_min = max(0, (agora - inicio_turno).total_seconds() / 60.0)
    
    # Se já passou do fim do turno, limita ao total
    if agora > fim_turno:
        tempo_decorrido_min = tempo_total_min

    meta_atual = int(tempo_decorrido_min * velocidade_otimista)

    # Status
    status = "ON_TRACK"
    if meta > 0:
        # Prioridade: Status atual (Produzido vs Esperado Agora)
        if produzido >= meta_atual:
            status = "ON_TRACK"
            # Se estiver significativamente adiantado (> 5%)
            if meta_atual > 0 and produzido > meta_atual * 1.05:
                status = "AHEAD"
        else:
            # Se estiver atrasado no momento, verifica projeção final
            if projecao_realista < meta * 0.95:
                status = "RISK"
            if projecao_realista < meta * 0.85:
                status = "DELAYED"
            if projecao_realista >= meta:
                # Recuperação projetada (está atrasado agora, mas velocidade atual recupera)
                status = "ON_TRACK"

    return {
        "linha": linha.nome,
        "turno": turno_atual.nome,
        "op": op,
        "produzido": produzido,
        "meta": meta,
        "meta_atual": meta_atual,
        "projecao_realista": int(projecao_realista),
        "projecao_otimista": int(projecao_otimista),
        "velocidade_atual": round(velocidade_real, 1),
        "velocidade_planejada": round(velocidade_planejada, 1),
        "tempo_restante_min": int(tempo_restante_min),
        "status": status
    }