"""
OPCVelocidadeWorker — lê velocidade e formato atual de cada linha via OPC UA.

Regras:
  • Lê tag_velocidade_opc e tag_formato_opc de cada linha
  • Só insere LeituraVelocidade se a velocidade for diferente da última
    para a mesma (linha, formato_gramas) — evita acúmulo de registros iguais
  • Ignora linhas sem tag_velocidade_opc configurada
  • Não lança exceção se o servidor OPC estiver offline
"""
import os
import threading
import logging

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_SEC = int(os.getenv('ANDRETTI_INTERVALO_LEITURA_MIN', '5')) * 60


class OPCVelocidadeWorker(threading.Thread):
    """Thread daemon que lê velocidade das linhas produtivas via OPC UA."""

    def __init__(self, interval=DEFAULT_INTERVAL_SEC):
        super().__init__()
        self.interval = interval
        self.daemon = True
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        logger.info(
            f"[Andretti] OPCVelocidadeWorker iniciado — "
            f"intervalo={self.interval}s ({self.interval // 60} min)"
        )
        from opcua import Client
        while not self._stop_event.is_set():
            try:
                self._ciclo_leitura(Client)
            except Exception as e:
                logger.error(f"[Andretti] Erro geral no ciclo: {e}")
            self._stop_event.wait(self.interval)

    def _ciclo_leitura(self, Client):
        from ips.models import Linha
        from .models import LeituraVelocidade

        linhas = (
            Linha.objects
            .filter(ativa=True, tag_velocidade_opc__isnull=False)
            .exclude(tag_velocidade_opc='')
        )

        if not linhas.exists():
            logger.debug("[Andretti] Nenhuma linha com tag_velocidade_opc configurada.")
            return

        # Agrupa por servidor OPC
        grupos = {}
        for linha in linhas:
            equip = (
                linha.equipamentos
                .filter(ativa=True, conexao_opcua__isnull=False)
                .select_related('conexao_opcua')
                .first()
            )
            if equip and equip.conexao_opcua:
                url = equip.conexao_opcua.url
                timeout = equip.conexao_opcua.timeout or 5
                grupos.setdefault(url, {'timeout': timeout, 'linhas': []})['linhas'].append(linha)
            else:
                logger.debug(f"[Andretti] {linha.nome}: sem servidor OPC configurado.")

        for url, info in grupos.items():
            client = None
            try:
                client = Client(url, timeout=info['timeout'])
                client.connect()

                for linha in info['linhas']:
                    try:
                        # Lê velocidade
                        vel_node = client.get_node(linha.tag_velocidade_opc)
                        velocidade = round(float(vel_node.get_value()), 2)

                        # Lê formato (gramas), se tag configurada
                        formato_gramas = None
                        if linha.tag_formato_opc:
                            try:
                                fmt_node = client.get_node(linha.tag_formato_opc)
                                formato_gramas = int(float(fmt_node.get_value()))
                            except Exception as e_fmt:
                                logger.debug(f"[Andretti] {linha.nome}: erro lendo formato OPC: {e_fmt}")

                        # Dedup: só insere se velocidade mudou para esta (linha, formato)
                        ultima = (
                            LeituraVelocidade.objects
                            .filter(linha=linha, formato_gramas=formato_gramas)
                            .order_by('-timestamp')
                            .values('velocidade')
                            .first()
                        )
                        vel_ultima = float(ultima['velocidade']) if ultima and ultima['velocidade'] is not None else None

                        if vel_ultima is None or abs(velocidade - vel_ultima) >= 0.1:
                            LeituraVelocidade.objects.create(
                                linha=linha,
                                velocidade=velocidade,
                                fonte='OPC',
                                formato_gramas=formato_gramas,
                            )
                            logger.info(
                                f"[Andretti] {linha.nome} [{formato_gramas}g]: "
                                f"{velocidade:.1f} ppm registrado"
                            )
                        else:
                            logger.debug(
                                f"[Andretti] {linha.nome} [{formato_gramas}g]: "
                                f"velocidade inalterada ({velocidade:.1f}), ignorado."
                            )

                    except Exception as e_node:
                        logger.warning(f"[Andretti] Erro na tag {linha.tag_velocidade_opc} ({linha.nome}): {e_node}")

            except Exception as e_conn:
                logger.warning(f"[Andretti] Servidor OPC inacessível {url}: {e_conn}")
            finally:
                if client:
                    try:
                        client.disconnect()
                    except Exception:
                        pass


def start_andretti_opc_worker():
    """Inicia o worker de leitura de velocidade. Chamado pelo apps.py."""
    worker = OPCVelocidadeWorker()
    worker.start()
    return worker
