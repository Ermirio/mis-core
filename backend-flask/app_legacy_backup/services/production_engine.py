import logging
import requests
from datetime import datetime, time

logger = logging.getLogger(__name__)

class ShiftManager:
    def __init__(self, django_url):
        self.django_url = django_url
        self.turnos = [] # Lista em memória RAM (atualizada via evento)
        
        # Carrega a primeira vez ao iniciar
        self.forcar_atualizacao()

    def forcar_atualizacao(self):
        """
        Vai ao Django buscar a configuração REAL.
        Não usa cache de tempo. É chamado no boot ou via Webhook.
        """
        try:
            # Endpoint do Django que lista os turnos ativos
            url = f"{self.django_url}/turnos/?ativo=true"
            logger.info(f"🔄 Sincronizando turnos com Django: {url}")
            
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                lista = data.get('results', data) if isinstance(data, dict) else data
                
                parsed = []
                for t in lista:
                    try:
                        # Converte strings "06:00:00" para objetos Time
                        inicio = datetime.strptime(t['hora_inicio'], '%H:%M:%S').time()
                        fim = datetime.strptime(t['hora_fim'], '%H:%M:%S').time()
                        parsed.append({
                            'id': t['id'],
                            'nome': t['nome'], 
                            'inicio': inicio, 
                            'fim': fim
                        })
                    except Exception as e:
                        logger.error(f"Erro ao processar turno {t}: {e}")

                self.turnos = parsed
                logger.info(f"✅ Turnos Carregados: {[t['nome'] for t in self.turnos]}")
                return True
            else:
                logger.error(f"Erro Django: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Falha de conexão com Django: {e}")
            return False

    def get_turno_atual(self):
        """
        Verifica matematicamente qual turno bate com a hora atual.
        ZERO regras fixas (hardcoded). Se não houver no Django, retorna None.
        """
        if not self.turnos:
            return "Sem Turno Configurado"

        now = datetime.now().time()
        
        for t in self.turnos:
            # Lógica para turnos que cruzam a meia-noite (Ex: 22:00 as 06:00)
            if t['inicio'] > t['fim']: 
                if now >= t['inicio'] or now < t['fim']:
                    return t['nome']
            # Lógica normal (Ex: 06:00 as 14:00)
            else:
                if t['inicio'] <= now < t['fim']:
                    return t['nome']
        
        return "Fora de Turno"

class ProductionEngine:
    def __init__(self, influx_client, django_api_url):
        self.client = influx_client
        # Inicializa o gerenciador passando a URL do Django
        self.shift_manager = ShiftManager(django_api_url)
        self._cache = {}

    def recarregar_configuracoes(self):
        """Método público para ser chamado via API (Webhook)"""
        return self.shift_manager.forcar_atualizacao()

    def _get_state(self, equipment_code):
        if equipment_code not in self._cache:
            self._cache[equipment_code] = {
                'last_raw': None,
                'op_code': None,
                'acc_op': 0,
                'shift_code': None,
                'acc_shift': 0,
                'initialized': False
            }
        return self._cache[equipment_code]

    def _load_state_from_db(self, eq, current_op, current_shift):
        state = self._get_state(eq)
        if state['initialized']: return

        try:
            query = f"""
                SELECT last(producao_op_acumulada), last(producao_turno_acumulada), 
                       last(ordem_producao_field), last(shift)
                FROM production WHERE "equipment" = '{eq}'
            """
            rs = self.client.query(query)
            points = list(rs.get_points())
            
            if points:
                d = points[0]
                # Só recupera acumulado se a OP for a mesma
                if d.get('last_ordem_producao_field') == current_op:
                    state['acc_op'] = int(d.get('last_producao_op_acumulada', 0))
                
                # Só recupera acumulado se o Turno for o mesmo
                if d.get('last_shift') == current_shift:
                    state['acc_shift'] = int(d.get('last_producao_turno_acumulada', 0))
                
                state['op_code'] = current_op
                state['shift_code'] = current_shift
            
            state['initialized'] = True
        except:
            state['initialized'] = True

    def processar_dados(self, equipamento, op_atual, contagem_bruta, descarte, formato_gramas, planejado):
        # 1. Pergunta ao Manager qual é o turno AGORA (baseado na config do Django)
        turno_atual = self.shift_manager.get_turno_atual()

        # 2. Carrega/Inicializa memória
        self._load_state_from_db(equipamento, op_atual, turno_atual)
        state = self._get_state(equipamento)
        
        # 3. Detecta Mudanças
        if op_atual != state['op_code']:
            logger.info(f"🔀 Nova OP ({op_atual}). Reset OP.")
            state['acc_op'] = 0
            state['op_code'] = op_atual
            
        if turno_atual != state['shift_code']:
            logger.info(f"🕒 Novo Turno ({turno_atual}). Reset Turno.")
            state['acc_shift'] = 0
            state['shift_code'] = turno_atual

        # 4. Calcula Delta
        delta = 0
        if state['last_raw'] is not None:
            delta = max(0, contagem_bruta - state['last_raw'])
            if delta < 0: delta = contagem_bruta # Reset físico
        
        state['last_raw'] = contagem_bruta

        # 5. Acumula
        state['acc_op'] += delta
        
        # Só acumula no turno se estivermos num turno válido
        if turno_atual not in ["Sem Turno Configurado", "Fora de Turno"]:
            state['acc_shift'] += delta
        
        # 6. Prepara retorno
        total_op = state['acc_op']
        ton_op = (total_op * formato_gramas) / 1_000_000.0 if formato_gramas else 0
        dif_op = total_op - planejado
        
        total_turno = state['acc_shift']
        ton_turno = (total_turno * formato_gramas) / 1_000_000.0 if formato_gramas else 0
        
        return {
            'producao_op': int(total_op),
            'toneladas_op': float(ton_op),
            'diferenca_op': int(dif_op),
            'producao_turno': int(total_turno),
            'toneladas_turno': float(ton_turno),
            'turno_atual_nome': turno_atual
        }

# Singleton
engine = None
def get_engine(client, django_url):
    global engine
    if engine is None:
        engine = ProductionEngine(client, django_api_url=django_url)
    return engine