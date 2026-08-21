import time
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from influxdb import InfluxDBClient
from decouple import config

from equipamentos.models import LinhaProducao, Equipamento, MetricaProducao, TurnoProducao

# Configuração de Logging
logger = logging.getLogger('MonitorVazao')

class Command(BaseCommand):
    help = 'Monitora e calcula vazão e tonelagem em tempo real (minuto a minuto)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configuração InfluxDB (Replicando do agregador)
        self.influx_client = InfluxDBClient(
            host=config('INFLUXDB_HOST', default='127.0.0.1'),
            port=config('INFLUXDB_PORT', default=8086, cast=int),
            username=config('INFLUXDB_USER', default=None),
            password=config('INFLUXDB_USER_PASSWORD', default=None),
            database=config('INFLUXDB_DATABASE', default='industrial_db')
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando monitoramento de vazão e tonelagem...'))
        
        while True:
            try:
                self.processar_ciclo()
            except Exception as e:
                logger.error(f"Erro no ciclo de monitoramento: {e}")
                self.stdout.write(self.style.ERROR(f"Erro: {e}"))
            
            # Aguarda 60 segundos antes do próximo ciclo
            time.sleep(60)

    def processar_ciclo(self):
        agora = timezone.now()
        linhas = LinhaProducao.objects.filter(ativa=True)

        for linha in linhas:
            self.processar_linha(linha, agora)

    def processar_linha(self, linha, agora):
        # 1. Identificar Equipamento Final Efetivo (último com tags ativas)
        equipamentos_asc = Equipamento.objects.filter(linha=linha, status='ATIVO').order_by('ordem_na_linha')
        equipamento_final = equipamentos_asc.filter(tags_coleta__ativa=True).distinct().last()

        if not equipamento_final:
            return

        # 2. Identificar Formato (primeiro com formato configurado)
        formato = None
        for eq in equipamentos_asc:
            tag_formato = eq.tags_coleta.filter(formato__gt=0).first()
            if tag_formato:
                formato = float(tag_formato.formato)
                break
        
        if not formato:
            return

        # 3. Buscar Contagens no InfluxDB
        # Precisamos de:
        # - Contagem Atual (para Tonelagem Turno)
        # - Contagem 1 min atrás (para Vazão)
        # - Contagem Início Turno (para Tonelagem Turno)

        turno_atual = self.get_turno_atual(agora)
        if not turno_atual:
            return

        # Define início do turno (considerando virada de dia se necessário)
        inicio_turno = agora.replace(hour=turno_atual.hora_inicio.hour, minute=turno_atual.hora_inicio.minute, second=0, microsecond=0)
        if inicio_turno > agora:
            inicio_turno -= timedelta(days=1)

        # Queries InfluxDB
        # O coletor/flask salva na measurement 'producao' com tag 'equipamento_codigo'
        
        # Query Contagem Atual (Last)
        query_atual = f"""
            SELECT last("contagem_saida") 
            FROM "producao" 
            WHERE "equipamento_codigo" = '{equipamento_final.codigo}' 
            AND time >= now() - 5m
        """
        
        # Query Contagem 1 min atrás
        query_1min = f"""
            SELECT first("contagem_saida") 
            FROM "producao" 
            WHERE "equipamento_codigo" = '{equipamento_final.codigo}' 
            AND time >= now() - 1m
        """

        # Query Contagem Início Turno
        query_inicio_turno = f"""
            SELECT first("contagem_saida") 
            FROM "producao" 
            WHERE "equipamento_codigo" = '{equipamento_final.codigo}' 
            AND time >= '{inicio_turno.isoformat()}'
        """

        try:
            # Debug
            self.stdout.write(f"DEBUG: Eq={equipamento_final.codigo}, InicioTurno={inicio_turno}, Agora={agora}")
            
            rs_atual = self.influx_client.query(query_atual)
            rs_1min = self.influx_client.query(query_1min)
            rs_inicio = self.influx_client.query(query_inicio_turno)

            val_atual = next(rs_atual.get_points(), {}).get('last', 0)
            val_1min = next(rs_1min.get_points(), {}).get('first', val_atual)
            
            points_inicio = list(rs_inicio.get_points())
            if points_inicio:
                val_inicio = points_inicio[0].get('first', val_atual)
            else:
                val_inicio = val_atual
                self.stdout.write(f"DEBUG: Sem dados inicio turno. Query: {query_inicio_turno}")

            # Vazão (Ton/Hora)
            delta_pecas_min = max(0, val_atual - val_1min)
            peso_min_ton = (delta_pecas_min * formato) / 1_000_000.0
            vazao_ton_hora = peso_min_ton * 60.0

            # Tonelagem Turno
            # Se val_atual < val_inicio, houve reset do contador
            # Neste caso, usamos val_atual como produção do turno
            if val_atual < val_inicio:
                # Reset detectado - usa valor atual como produção
                delta_pecas_turno = val_atual
                self.stdout.write(f"⚠️ Reset detectado: usando contagem atual ({val_atual}) como produção do turno")
            else:
                # Normal - calcula delta
                delta_pecas_turno = val_atual - val_inicio
            
            toneladas_turno = (delta_pecas_turno * formato) / 1_000_000.0
            
            self.stdout.write(f"DEBUG: DeltaMin={delta_pecas_min}, DeltaTurno={delta_pecas_turno}, ValAtual={val_atual}, ValInicio={val_inicio}")

            # 5. Atualizar SQL (MetricaProducao)
            # Busca a métrica mais recente do turno para atualizar
            metrica_sql = MetricaProducao.objects.filter(
                equipamento=equipamento_final,
                linha=linha,
                periodo='TURNO',
                turno=turno_atual.nome
            ).order_by('-data_hora').first()

            if metrica_sql:
                from decimal import Decimal
                metrica_sql.contagem_saida = val_atual
                metrica_sql.toneladas_produzidas = Decimal(str(toneladas_turno))
                metrica_sql.vazao_real_ton_hora = Decimal(str(vazao_ton_hora))
                metrica_sql.formato_gramas = Decimal(str(formato))
                metrica_sql.save()
                self.stdout.write(f"✅ Métrica atualizada: Ton={toneladas_turno:.3f}t, Vazão={vazao_ton_hora:.2f}t/h")
            else:
                # Se não existir, cria uma nova com data_hora = inicio_turno
                from decimal import Decimal
                MetricaProducao.objects.create(
                    equipamento=equipamento_final,
                    linha=linha,
                    periodo='TURNO',
                    data_hora=inicio_turno,
                    turno=turno_atual.nome,
                    contagem_saida=val_atual,
                    toneladas_produzidas=Decimal(str(toneladas_turno)),
                    vazao_real_ton_hora=Decimal(str(vazao_ton_hora)),
                    formato_gramas=Decimal(str(formato))
                )
                self.stdout.write(f"✅ Métrica criada: Ton={toneladas_turno:.3f}t, Vazão={vazao_ton_hora:.2f}t/h")
            
            # 6. Salvar métrica consolidada da LINHA (para endpoints de tonelagem)
            # Os endpoints tonnage_views.py buscam com equipamento__isnull=True
            metrica_linha = MetricaProducao.objects.filter(
                linha=linha,
                equipamento__isnull=True,  # Métrica consolidada da linha
                periodo='TURNO',
                data_hora=inicio_turno
            ).first()

            if metrica_linha:
                # Atualizar existente
                metrica_linha.contagem_saida = val_atual
                metrica_linha.toneladas_produzidas = Decimal(str(toneladas_turno))
                metrica_linha.vazao_real_ton_hora = Decimal(str(vazao_ton_hora))
                metrica_linha.formato_gramas = Decimal(str(formato))
                metrica_linha.save()
                self.stdout.write(f"✅ Métrica LINHA atualizada: Ton={toneladas_turno:.3f}t")
            else:
                # Criar nova métrica consolidada da linha
                MetricaProducao.objects.create(
                    linha=linha,
                    equipamento=None,  # NULL = métrica consolidada da linha
                    periodo='TURNO',
                    data_hora=inicio_turno,
                    turno=turno_atual.nome,
                    contagem_saida=val_atual,
                    toneladas_produzidas=Decimal(str(toneladas_turno)),
                    vazao_real_ton_hora=Decimal(str(vazao_ton_hora)),
                    formato_gramas=Decimal(str(formato))
                )
                self.stdout.write(f"✅ Métrica LINHA criada: Ton={toneladas_turno:.3f}t")
            
            # 6b. Salvar métrica consolidada da LINHA para HORA (para endpoint tempo real)
            # O endpoint tonelagem_tempo_real busca período='HORA'
            hora_atual = agora.replace(minute=0, second=0, microsecond=0)
            
            metrica_linha_hora = MetricaProducao.objects.filter(
                linha=linha,
                equipamento__isnull=True,
                periodo='HORA',
                data_hora=hora_atual
            ).first()
            
            if metrica_linha_hora:
                # Atualizar existente
                metrica_linha_hora.contagem_saida = val_atual
                metrica_linha_hora.toneladas_produzidas = Decimal(str(toneladas_turno))
                metrica_linha_hora.vazao_real_ton_hora = Decimal(str(vazao_ton_hora))
                metrica_linha_hora.formato_gramas = Decimal(str(formato))
                metrica_linha_hora.save()
                self.stdout.write(f"✅ Métrica LINHA HORA atualizada: Vazão={vazao_ton_hora:.2f}t/h")
            else:
                # Criar nova métrica consolidada da linha para HORA
                MetricaProducao.objects.create(
                    linha=linha,
                    equipamento=None,
                    periodo='HORA',
                    data_hora=hora_atual,
                    turno=turno_atual.nome,
                    contagem_saida=val_atual,
                    toneladas_produzidas=Decimal(str(toneladas_turno)),
                    vazao_real_ton_hora=Decimal(str(vazao_ton_hora)),
                    formato_gramas=Decimal(str(formato))
                )
                self.stdout.write(f"✅ Métrica LINHA HORA criada: Vazão={vazao_ton_hora:.2f}t/h")
            
            # 7. Gravar no InfluxDB (Tendência)
            point = {
                "measurement": "metricas_linha_tempo_real",
                "tags": {
                    "linha_id": linha.id,
                    "linha_codigo": linha.codigo,
                    "equipamento_final": equipamento_final.nome
                },
                "time": agora.isoformat(),
                "fields": {
                    "vazao_ton_hora": float(vazao_ton_hora),
                    "toneladas_turno": float(toneladas_turno),
                    "formato": float(formato)
                }
            }
            self.influx_client.write_points([point])
            
            self.stdout.write(f"Linha {linha.codigo}: Vazão={vazao_ton_hora:.2f} t/h, Ton={toneladas_turno:.3f} t")

        except Exception as e:
            logger.error(f"Erro ao processar linha {linha.codigo}: {e}")

    def get_turno_atual(self, agora):
        # Lógica simplificada para encontrar turno atual
        # Idealmente deveria lidar com virada de dia e múltiplos turnos
        # Aqui pegamos o primeiro ativo que engloba a hora atual
        hora_atual = agora.time()
        turnos = TurnoProducao.objects.filter(ativo=True)
        
        for turno in turnos:
            if turno.hora_inicio <= turno.hora_fim:
                if turno.hora_inicio <= hora_atual <= turno.hora_fim:
                    return turno
            else: # Vira o dia (ex: 22:00 as 06:00)
                if hora_atual >= turno.hora_inicio or hora_atual <= turno.hora_fim:
                    return turno
        
        return None
