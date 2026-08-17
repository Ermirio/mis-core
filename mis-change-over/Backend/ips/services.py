import time
import threading
import logging
from opcua import Client, ua
from django.db import transaction

logger = logging.getLogger(__name__)


def write_opc_node(url, node_id, value, timeout=5):
    """
    Escreve um valor booleano em um nó OPC UA.
    Retorna (success: bool, error: str|None)
    """
    client = Client(url, timeout=timeout)
    try:
        client.connect()
        node = client.get_node(node_id)
        node.set_value(ua.DataValue(ua.Variant(bool(value), ua.VariantType.Boolean)))
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

class OPCIntertravamentoWorker(threading.Thread):
    def __init__(self, interval=5):
        super().__init__()
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def connect_client(self, url):
        client = Client(url, timeout=5)
        client.connect()
        return client

    def run(self):
        logger.info("Iniciando serviço OPC Múltiplo para Intertravamentos...")
        # Import atrasado para garantir que os apps estejam carregados
        from .models import IntertravamentoLinha
        
        while not self._stop_event.is_set():
            try:
                # Agrupar intertravamentos por URL do servidor para minimizar conexões
                # Buscamos apenas linhas habilitadas do software
                intertravamentos = IntertravamentoLinha.objects.select_related('conexao_opcua').all()
                url_dict = {}
                for inter in intertravamentos:
                    if inter.conexao_opcua and inter.node_id_tag:
                        url = inter.conexao_opcua.url
                        if url not in url_dict:
                            url_dict[url] = []
                        url_dict[url].append(inter)

                for url, itens in url_dict.items():
                    client = None
                    try:
                        client = self.connect_client(url)
                        for item in itens:
                            try:
                                # node_id_tag já contém o endereço OPC completo
                                node = client.get_node(item.node_id_tag)
                                val = node.get_value()
                                val_bool = bool(val)
                                if item.estado_opc != val_bool:
                                    valor_anterior = item.estado_opc if item.estado_opc is not None else False
                                    item.estado_opc = val_bool
                                    item.save(update_fields=['estado_opc'])
                                    # Registra log quando o CLP altera o estado fora do frontend.
                                    # Janela de 10s evita duplicatas causadas pelos múltiplos workers gunicorn
                                    # (cada worker tem sua própria thread OPC e pode detectar a mudança ao mesmo tempo).
                                    from .models import HistoricoIntertravamento
                                    from django.utils import timezone
                                    from datetime import timedelta
                                    ja_registrado = HistoricoIntertravamento.objects.filter(
                                        intertravamento=item,
                                        origem='OPC',
                                        valor_novo=val_bool,
                                        timestamp__gte=timezone.now() - timedelta(seconds=10)
                                    ).exists()
                                    if not ja_registrado:
                                        HistoricoIntertravamento.objects.create(
                                            intertravamento=item,
                                            campo='estado_opc',
                                            valor_anterior=valor_anterior,
                                            valor_novo=val_bool,
                                            origem='OPC',
                                            usuario=None,
                                            observacao='Estado alterado diretamente no CLP (leitura OPC UA)'
                                        )
                            except Exception as e_node:
                                # Conseguiu conectar ao servidor mas falhou ao ler o nó específico
                                # → tag inexistente ou erro de leitura → marcar como offline (False)
                                logger.warning(f"Erro lendo nó {item.node_id_tag} em {url}: {e_node}")
                                if item.estado_opc is not False:
                                    item.estado_opc = False
                                    item.save(update_fields=['estado_opc'])

                    except Exception as e_conn:
                        # Servidor OPC inacessível → não alterar estado_opc (último valor conhecido)
                        logger.warning(f"Servidor OPC inacessível {url}: {e_conn}")
                    finally:
                        if client:
                            try:
                                client.disconnect()
                            except:
                                pass
                                
            except Exception as e:
                logger.error(f"Erro geral no loop de Intertravamentos: {e}")
            
            # Aguardar próximo tick
            self._stop_event.wait(self.interval)

def start_opc_service():
    worker = OPCIntertravamentoWorker(interval=4)
    worker.start()
    return worker


# ==================== WORKER VALIDAÇÃO QUALIDADE v9.0 ====================

def _read_tag_value(client, node_id):
    """Lê um nó OPC UA. Retorna (valor, ok: bool)."""
    try:
        node = client.get_node(node_id)
        return node.get_value(), True
    except Exception:
        return None, False


class OPCValidacaoQualidadeWorker(threading.Thread):
    """
    Worker que:
    1. Lê tag_status_linha_opc e tag_sku_atual_opc de cada linha ativa.
    2. Acumula tempo de produção real (status=10, SKU bate) em ValidacaoQualidade.
    3. Escreve True em tag_aguardando_validacao_opc ao esgotar o prazo.
    4. Registra intervalos de status em HistoricoStatusLinha.
    """

    INTERVAL = 5  # segundos entre cada ciclo

    def __init__(self):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()
        # {linha_id: {'hist_id': int, 'status_codigo': int, 'sku': str, 'iniciado_em': datetime}}
        self._historico_aberto: dict = {}

    def stop(self):
        self._stop_event.set()

    # ── HistoricoStatusLinha helpers ──────────────────────────────────────

    def _fechar_historico(self, linha_id, agora):
        info = self._historico_aberto.pop(linha_id, None)
        if not info or not info.get('hist_id'):
            return
        try:
            from .models import HistoricoStatusLinha
            delta = (agora - info['iniciado_em']).total_seconds()
            HistoricoStatusLinha.objects.filter(pk=info['hist_id']).update(
                encerrado_em=agora,
                duracao_s=round(delta, 1),
            )
        except Exception as e:
            logger.warning(f"[VQ-Worker] Erro ao fechar HistoricoStatusLinha {info['hist_id']}: {e}")

    def _abrir_historico(self, linha, status_codigo, sku, agora):
        try:
            from .models import HistoricoStatusLinha
            hist = HistoricoStatusLinha.objects.create(
                linha=linha,
                status_codigo=status_codigo,
                sku_em_operacao=sku or '',
                iniciado_em=agora,
            )
            self._historico_aberto[linha.id] = {
                'hist_id': hist.id,
                'status_codigo': status_codigo,
                'sku': sku,
                'iniciado_em': agora,
            }
        except Exception as e:
            logger.warning(f"[VQ-Worker] Erro ao criar HistoricoStatusLinha para {linha.nome}: {e}")

    # ── ValidacaoQualidade timer ──────────────────────────────────────────

    def _processar_validacao(self, linha, status_codigo, sku_atual, caixas_produzidas, agora):
        """
        Validação por CAIXAS (v11.0): compara o contador de caixas desde a troca
        (tag_caixas_sku_opc) com a meta. Ao atingir a meta, escreve True em
        tag_aguardando_validacao_opc (CLP para em fail-safe) e registra histórico.

        `caixas_produzidas` é None quando a tag não está configurada ou falhou —
        nesse caso não há como validar por caixas, então não faz nada.
        """
        from .models import ValidacaoQualidade, HistoricoValidacaoQualidade
        try:
            vq = (
                ValidacaoQualidade.objects
                .filter(linha=linha, status=ValidacaoQualidade.StatusValidacao.PENDENTE)
                .select_related('produto')
                .first()
            )
        except Exception as e:
            logger.warning(f"[VQ-Worker] Erro ao buscar ValidacaoQualidade {linha.nome}: {e}")
            return

        if not vq:
            return

        # Sem meta configurada (0) → não valida por caixas.
        if not vq.quantidade_caixas_meta:
            return

        # Sem leitura de caixas → não há como avançar.
        if caixas_produzidas is None:
            return

        # Só conta quando o SKU em operação bate com o da validação (segurança:
        # evita contar caixas de outro SKU se a leitura de sku_atual estiver ok).
        if sku_atual and sku_atual != vq.produto.sku:
            return

        update_fields = ['caixas_produzidas', 'ultima_leitura_opc', 'atualizada_em']
        vq.caixas_produzidas = int(caixas_produzidas)
        vq.ultima_leitura_opc = agora

        # Meta atingida → sinalizar parada (uma única vez).
        if not vq.opc_sinal_enviado and vq.caixas_produzidas >= vq.quantidade_caixas_meta:
            ok = False
            err = None
            if linha.conexao_opc_status and linha.tag_aguardando_validacao_opc:
                ok, err = write_opc_node(
                    linha.conexao_opc_status.url,
                    linha.tag_aguardando_validacao_opc,
                    True,
                )
                if ok:
                    logger.info(
                        f"[VQ-Worker] Meta atingida → OPC TRUE (parar) "
                        f"{linha.nome} / {vq.produto.sku} "
                        f"({vq.caixas_produzidas}/{vq.quantidade_caixas_meta} caixas)"
                    )
                else:
                    logger.warning(
                        f"[VQ-Worker] Falha ao escrever OPC {linha.tag_aguardando_validacao_opc}: {err}"
                    )
            else:
                logger.warning(
                    f"[VQ-Worker] {linha.nome}: meta atingida mas conexao_opc_status "
                    "ou tag_aguardando_validacao_opc não configurados."
                )

            vq.opc_sinal_enviado = True
            vq.parada_em = agora
            vq.status = ValidacaoQualidade.StatusValidacao.EXPIRADO  # 'aguardando qualidade'
            update_fields += ['opc_sinal_enviado', 'parada_em', 'status']

            # Tracking: meta atingida (e resultado da escrita OPC)
            try:
                HistoricoValidacaoQualidade.objects.create(
                    validacao=vq,
                    evento=HistoricoValidacaoQualidade.Evento.META_ATINGIDA,
                    caixas_no_momento=vq.caixas_produzidas,
                    meta_caixas=vq.quantidade_caixas_meta,
                    observacao=(f'Linha sinalizada para parar. '
                                + ('OPC: True enviado.' if ok else f'OPC: FALHA ({err}).')),
                )
                if not ok:
                    HistoricoValidacaoQualidade.objects.create(
                        validacao=vq,
                        evento=HistoricoValidacaoQualidade.Evento.FALHA_OPC,
                        caixas_no_momento=vq.caixas_produzidas,
                        meta_caixas=vq.quantidade_caixas_meta,
                        observacao=str(err or 'tags não configuradas'),
                    )
            except Exception as e:
                logger.warning(f"[VQ-Worker] Erro ao gravar histórico VQ #{vq.id}: {e}")

        try:
            vq.save(update_fields=list(set(update_fields)))
        except Exception as e:
            logger.warning(f"[VQ-Worker] Erro ao salvar ValidacaoQualidade #{vq.id}: {e}")

    # ── Main loop ─────────────────────────────────────────────────────────

    def _processar_linha(self, linha, client, agora):
        """Lê tags de uma linha e processa historico + validacao."""
        # Ler status
        status_val, ok_status = _read_tag_value(client, linha.tag_status_linha_opc)
        if not ok_status:
            # Servidor acessível mas tag falhou — não fechar historico, apenas logar
            logger.debug(f"[VQ-Worker] Falha ao ler tag_status {linha.nome}")
            return

        try:
            status_codigo = int(status_val)
        except (TypeError, ValueError):
            logger.debug(f"[VQ-Worker] Valor inesperado em tag_status {linha.nome}: {status_val!r}")
            return

        # Ler SKU atual (opcional — pode estar vazio)
        sku_atual = ''
        if linha.tag_sku_atual_opc:
            sku_val, ok_sku = _read_tag_value(client, linha.tag_sku_atual_opc)
            if ok_sku and sku_val is not None:
                sku_atual = str(sku_val).strip()

        # Ler contador de caixas desde a troca (validação por caixas v11.0)
        caixas_produzidas = None
        if linha.tag_caixas_sku_opc:
            caixas_val, ok_caixas = _read_tag_value(client, linha.tag_caixas_sku_opc)
            if ok_caixas and caixas_val is not None:
                try:
                    caixas_produzidas = int(caixas_val)
                except (TypeError, ValueError):
                    logger.debug(f"[VQ-Worker] Valor inesperado em tag_caixas {linha.nome}: {caixas_val!r}")

        # ── HistoricoStatusLinha ──────────────────────────────────────────
        anterior = self._historico_aberto.get(linha.id)
        if anterior is None:
            # Primeiro tick: abrir registro
            self._abrir_historico(linha, status_codigo, sku_atual, agora)
        elif anterior['status_codigo'] != status_codigo or anterior['sku'] != sku_atual:
            # Mudança de status ou SKU: fechar anterior e abrir novo
            self._fechar_historico(linha.id, agora)
            self._abrir_historico(linha, status_codigo, sku_atual, agora)

        # ── ValidacaoQualidade por caixas ─────────────────────────────────
        self._processar_validacao(linha, status_codigo, sku_atual, caixas_produzidas, agora)

    def run(self):
        logger.info("[VQ-Worker] Iniciando worker de Validação de Qualidade...")
        from .models import Linha, ValidacaoQualidade  # noqa: F401 (import tardio)

        while not self._stop_event.is_set():
            try:
                from django.utils import timezone as tz
                agora = tz.now()

                # Linhas ativas com servidor OPC de status configurado
                linhas = (
                    Linha.objects.filter(
                        ativa=True,
                        conexao_opc_status__isnull=False,
                        tag_status_linha_opc__isnull=False,
                    )
                    .exclude(tag_status_linha_opc='')
                    .select_related('conexao_opc_status')
                )

                # Agrupar por servidor para minimizar conexões
                por_servidor: dict = {}
                for linha in linhas:
                    url = linha.conexao_opc_status.url
                    por_servidor.setdefault(url, []).append(linha)

                for url, lista_linhas in por_servidor.items():
                    client = None
                    try:
                        client = Client(url, timeout=5)
                        client.connect()
                        for linha in lista_linhas:
                            try:
                                self._processar_linha(linha, client, agora)
                            except Exception as e_linha:
                                logger.warning(
                                    f"[VQ-Worker] Erro ao processar linha {linha.nome}: {e_linha}"
                                )
                    except Exception as e_conn:
                        logger.warning(f"[VQ-Worker] Servidor OPC inacessível {url}: {e_conn}")
                    finally:
                        if client:
                            try:
                                client.disconnect()
                            except Exception:
                                pass

            except Exception as e_global:
                logger.error(f"[VQ-Worker] Erro global no loop: {e_global}")

            self._stop_event.wait(self.INTERVAL)

        logger.info("[VQ-Worker] Worker encerrado.")


def start_validacao_qualidade_worker():
    worker = OPCValidacaoQualidadeWorker()
    worker.start()
    return worker


# ==================== EXPIRAÇÃO DE CONTAS DE USUÁRIO (item 3) ====================

def expirar_contas_vencidas():
    """
    Desativa (is_active=False) contas de usuários comuns que expiraram por
    inatividade (60 dias) ou validade (5 meses). Superusers nunca expiram.

    Idempotente: desativar conta já inativa não causa efeito. Retorna a lista
    de (username, motivo) desativados nesta execução.
    """
    from django.contrib.auth.models import User
    from .models import ContaUsuarioExpiracao

    desativados = []
    qs = ContaUsuarioExpiracao.objects.select_related('user').filter(
        user__is_active=True, user__is_superuser=False
    )
    for exp in qs:
        motivo = exp.motivo_expiracao()
        if motivo:
            exp.user.is_active = False
            exp.user.save(update_fields=['is_active'])
            desativados.append((exp.user.username, motivo))
            logger.info("[Expiracao] %s desativado por %s", exp.user.username, motivo)
    return desativados


class ExpiracaoContasWorker(threading.Thread):
    """Worker diário que desativa contas vencidas. Idempotente."""

    INTERVAL = 24 * 60 * 60  # 24h

    def __init__(self):
        super().__init__()
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info("[Expiracao] Worker de expiração de contas iniciado.")
        # Roda uma vez logo na partida, depois a cada 24h.
        while not self._stop_event.is_set():
            try:
                desativados = expirar_contas_vencidas()
                if desativados:
                    logger.info("[Expiracao] %d conta(s) desativada(s): %s",
                                len(desativados), desativados)
            except Exception as e:
                logger.error("[Expiracao] erro no loop: %s", e)
            self._stop_event.wait(self.INTERVAL)


def start_expiracao_contas_worker():
    worker = ExpiracaoContasWorker()
    worker.start()
    return worker
