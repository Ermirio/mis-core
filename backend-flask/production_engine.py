import logging
import requests
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ===== GERENCIADOR DE CONFIGURAÇÕES (Velocidades Nominais) =====
class ConfigManager:
    def __init__(self, django_url):
        self.django_url = django_url
        self.equipamentos = {} 
        self.last_update = 0
        self.CACHE_DURATION = 300  # 5 minutos

    def get_config(self, codigo):
        if time.time() - self.last_update > self.CACHE_DURATION:
            self._atualizar_cache()
        return self.equipamentos.get(codigo, {'vel_nominal': 100})

    def _atualizar_cache(self):
        try:
            url = f"{self.django_url}/equipamentos/"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                lista = data.get('results', data)
                
                novas_configs = {}
                for eq in lista:
                    novas_configs[eq['codigo']] = {
                        'vel_nominal': float(eq['velocidade_nominal'] or 1), 
                        'id': eq['id']
                    }
                self.equipamentos = novas_configs
                self.last_update = time.time()
                logger.info(f"[CONFIG] Configuracoes atualizadas: {len(self.equipamentos)} equipamentos")
        except Exception as e:
            logger.error(f"Erro ao buscar configs do Django: {e}")

# ===== GERENCIADOR DE TURNOS =====
class ShiftManager:
    def __init__(self, django_url):
        self.django_url = django_url
        self.turnos = []
        self.forcar_atualizacao()

    def forcar_atualizacao(self):
        try:
            url = f"{self.django_url}/turnos/?ativo=true"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                lista = data.get('results', data) if isinstance(data, dict) else data
                parsed = []
                for t in lista:
                    try:
                        inicio = datetime.strptime(t['hora_inicio'], '%H:%M:%S').time()
                        fim = datetime.strptime(t['hora_fim'], '%H:%M:%S').time()
                        parsed.append({'nome': t['nome'], 'inicio': inicio, 'fim': fim})
                    except: pass
                self.turnos = parsed
                logger.info(f"[TURNOS] Turnos carregados: {len(self.turnos)}")
                return True
            return False
        except: return False

    def get_turno_atual(self):
        """Retorna apenas o nome do turno (compatibilidade)"""
        turno_info = self.get_turno_info()
        return turno_info['nome'] if turno_info else "Fora de Turno"
    
    def get_turno_info(self):
        """
        Retorna informações completas do turno atual para cálculo temporal
        Returns:
            dict: {'nome': str, 'inicio': time, 'fim': time, 'inicio_timestamp': float}
            None: se não houver turno ativo
        """
        if not self.turnos:
            # Tenta recarregar se estiver vazio (pode ter falhado na inicialização)
            if time.time() - getattr(self, 'last_attempt', 0) > 60:
                self.last_attempt = time.time()
                self.forcar_atualizacao()
            
            if not self.turnos:
                return None
        
        now = datetime.now()
        now_time = now.time()
        
        for t in self.turnos:
            # Turno noturno (ex: 23:00-07:00)
            if t['inicio'] > t['fim']:
                if now_time >= t['inicio'] or now_time < t['fim']:
                    # Calcula quando o turno começou
                    if now_time >= t['inicio']:
                        # Turno começou hoje
                        turno_inicio_dt = datetime.combine(now.date(), t['inicio'])
                    else:
                        # Turno começou ontem
                        turno_inicio_dt = datetime.combine(now.date() - timedelta(days=1), t['inicio'])
                    
                    return {
                        'nome': t['nome'],
                        'inicio': t['inicio'],
                        'fim': t['fim'],
                        'inicio_timestamp': turno_inicio_dt.timestamp()
                    }
            # Turno diurno (ex: 07:00-15:00)
            else:
                if t['inicio'] <= now_time < t['fim']:
                    turno_inicio_dt = datetime.combine(now.date(), t['inicio'])
                    return {
                        'nome': t['nome'],
                        'inicio': t['inicio'],
                        'fim': t['fim'],
                        'inicio_timestamp': turno_inicio_dt.timestamp()
                    }
        
        return None  # Fora de turno

# ===== MOTOR DE PRODUÇÃO =====
class ProductionEngine:
    def __init__(self, influx_client, django_api_url):
        self.client = influx_client
        self.shift_manager = ShiftManager(django_api_url)
        self.config_manager = ConfigManager(django_api_url)
        self._cache = {}
        self.heartbeats = {} # {equipment_code: timestamp}
        self.MAX_TIME_DELTA = 300  # 5 minutos - proteção contra server offline

    def recarregar_configuracoes(self):
        self.config_manager._atualizar_cache()
        return self.shift_manager.forcar_atualizacao()

    def _get_state(self, equipment_code):
        if equipment_code not in self._cache:
            self._cache[equipment_code] = {
                # Acumuladores de produção
                'last_raw': None,
                'last_waste': None,
                'op_code': None,
                'acc_op': 0,
                'acc_waste_op': 0,
                'shift_code': None,
                'acc_shift': 0,
                
                # NOVOS: Campos temporais
                'last_timestamp': None,          # Timestamp da última medição
                'last_estado': None,             # Estado da máquina na última medição
                'shift_start_time': None,        # Quando o turno atual começou
                'acc_time_stop_shift': 0.0,      # Tempo parado acumulado no turno (segundos)
                'velocity_buffer': [],           # Buffer para média móvel de velocidade
                
                'initialized': False
            }
        return self._cache[equipment_code]

    def _load_state_from_db(self, eq, current_op, current_shift):
        state = self._get_state(eq)
        if state['initialized']: return

        try:
            query = f"SELECT * FROM production WHERE \"equipment\" = '{eq}' ORDER BY time DESC LIMIT 1"
            rs = self.client.query(query)
            points = list(rs.get_points())
            
            if points:
                d = points[0]
                
                # Normalização de strings
                last_op = str(d.get('order_id') or d.get('ordem_producao_field') or '').strip()
                curr_op = str(current_op or '').strip()
                last_shift = str(d.get('shift') or '').strip()
                curr_shift = str(current_shift or '').strip()

                # Recupera acumuladores se o contexto for o mesmo
                if last_op == curr_op:
                    state['acc_op'] = int(d.get('producao_op_acumulada', 0) or 0)
                    state['acc_waste_op'] = int(d.get('refugo_op_acumulado', 0) or 0)
                
                if last_shift == curr_shift:
                    state['acc_shift'] = int(d.get('producao_turno_acumulada', 0) or 0)
                    # NOVO: Recupera tempo parado do turno
                    state['acc_time_stop_shift'] = float(d.get('tempo_parado_turno', 0) or 0)
                
                # Recupera referências brutas para cálculo de delta
                raw_val = d.get('contagem_saida')
                if raw_val is not None: state['last_raw'] = int(raw_val)
                
                waste_val = d.get('descarte')
                if waste_val is not None: state['last_waste'] = int(waste_val)
                
                # NOVO: Recupera timestamp e estado
                timestamp_val = d.get('timestamp_medicao')
                if timestamp_val: state['last_timestamp'] = float(timestamp_val)
                
                estado_val = d.get('estado_maquina')
                if estado_val is not None: state['last_estado'] = int(estado_val)
                
                state['op_code'] = current_op
                state['shift_code'] = current_shift
            
            state['initialized'] = True
        except Exception as e:
            logger.error(f"Erro load state: {e}")
            state['initialized'] = True

    def processar_dados(self, equipamento, op_atual, contagem_bruta, descarte, formato_gramas, planejado, velocidade_atual, estado_maquina):
        # 1. Contexto
        now_timestamp = time.time()
        turno_info = self.shift_manager.get_turno_info()
        turno_atual = turno_info['nome'] if turno_info else "Fora de Turno"
        
        config = self.config_manager.get_config(equipamento)
        vel_nominal = config['vel_nominal']

        # Atualiza Heartbeat
        self.heartbeats[equipamento] = now_timestamp

        # 2. Inicializa memória
        self._load_state_from_db(equipamento, op_atual, turno_atual)
        state = self._get_state(equipamento)
        
        # 3. Detecta Mudanças de Contexto (OP/Turno)
        if str(op_atual).strip() != str(state['op_code']).strip():
            state['acc_op'] = 0
            state['acc_waste_op'] = 0
            state['op_code'] = op_atual
        
        # Mudança de turno: Zera acumuladores se o nome mudou OU se a data do início do turno mudou
        shift_changed = False
        current_shift_start = turno_info['inicio_timestamp'] if turno_info else None
        
        if str(turno_atual).strip() != str(state['shift_code']).strip():
            shift_changed = True
        elif current_shift_start and state['shift_start_time']:
            # Se o timestamp de início do turno mudou (ex: mesmo turno, outro dia)
            if abs(current_shift_start - state['shift_start_time']) > 60: # Margem de 1 min
                shift_changed = True

        if shift_changed:
            state['acc_shift'] = 0
            state['acc_time_stop_shift'] = 0.0
            state['shift_code'] = turno_atual
            state['shift_start_time'] = current_shift_start
        
        # Inicializa shift_start_time se necessário (primeira execução ou recuperado do banco sem timestamp)
        if turno_info and state['shift_start_time'] is None:
            state['shift_start_time'] = turno_info['inicio_timestamp']

        # 4. Cálculo de Delta de Tempo
        time_delta = 0.0
        if state['last_timestamp'] is not None:
            time_delta = now_timestamp - state['last_timestamp']
            # Proteção: Ignora delta muito grande (servidor reiniciou)
            if time_delta > self.MAX_TIME_DELTA or time_delta < 0:
                logger.warning(f"{equipamento}: Delta tempo anormal ({time_delta:.1f}s), ignorando")
                time_delta = 0.0
        
        # 5. Acumula Tempo Parado
        # Somente acumula se o ESTADO ANTERIOR era diferente de 1 (Produzindo)
        if state['last_estado'] is not None and time_delta > 0:
            if state['last_estado'] != 1:  # 1 = Produzindo
                state['acc_time_stop_shift'] += time_delta
                logger.debug(f"{equipamento}: +{time_delta:.1f}s parado (total: {state['acc_time_stop_shift']:.1f}s)")
        
        # Atualiza referências temporais
        state['last_timestamp'] = now_timestamp
        state['last_estado'] = estado_maquina

        # 6. Deltas de Produção e Refugo
        delta = 0
        if state['last_raw'] is not None:
            delta = max(0, contagem_bruta - state['last_raw'])
            if delta < 0: delta = contagem_bruta  # Reset físico
        state['last_raw'] = contagem_bruta

        delta_waste = 0
        if state['last_waste'] is not None:
            delta_waste = max(0, descarte - state['last_waste'])
            if delta_waste < 0: delta_waste = descarte  # Reset físico
        state['last_waste'] = descarte

        # 7. Acumuladores de Produção
        if delta > 0:
            state['acc_op'] += delta
            if turno_atual not in ["Sem Turno Configurado", "Fora de Turno"]:
                state['acc_shift'] += delta
        
        if delta_waste > 0:
            state['acc_waste_op'] += delta_waste
        
        # 8. CÁLCULO DE OEE
        # === DISPONIBILIDADE TEMPORAL ===
        disponibilidade = 0.0
        tempo_planejado = 0.0
        tempo_parado = state['acc_time_stop_shift']
        
        if turno_info and state['shift_start_time']:
            tempo_planejado = now_timestamp - state['shift_start_time']
            
            if tempo_planejado > 0:
                # Fórmula Temporal: (Planejado - Parado) / Planejado
                disponibilidade = (tempo_planejado - tempo_parado) / tempo_planejado
                disponibilidade = max(0.0, min(1.0, disponibilidade))
            else:
                # Turno começou há menos de 1s - usa estado instantâneo
                disponibilidade = 1.0 if estado_maquina == 1 else 0.0
        else:
            # Fallback: Sem turno configurado, usa estado instantâneo
            # Estados 1, 2, 3 = Produzindo, Aguardando, Bloqueado = Disponível
            disponibilidade = 1.0 if estado_maquina in [1, 2, 3] else 0.0
        
        # === PERFORMANCE ===
        # Média Móvel Simples (3 amostras)
        if 'velocity_buffer' not in state: state['velocity_buffer'] = []
        state['velocity_buffer'].append(velocidade_atual)
        if len(state['velocity_buffer']) > 3:
            state['velocity_buffer'].pop(0)
        
        avg_velocity = sum(state['velocity_buffer']) / len(state['velocity_buffer']) if state['velocity_buffer'] else 0
        
        performance = 0.0
        if vel_nominal > 0:
            performance = min(1.05, avg_velocity / vel_nominal)
        
        # === QUALIDADE ===
        total_prod_op = state['acc_op']
        total_waste_op = state['acc_waste_op']
        qualidade = 1.0
        
        if total_prod_op > 0:
            qualidade = max(0.0, (total_prod_op - total_waste_op) / total_prod_op)
        
        oee = disponibilidade * performance * qualidade * 100

        # 9. Totais
        ton_op = (total_prod_op * formato_gramas) / 1_000_000.0 if formato_gramas else 0
        dif_op = total_prod_op - planejado
        
        total_turno = state['acc_shift']
        ton_turno = (total_turno * formato_gramas) / 1_000_000.0 if formato_gramas else 0
        
        return {
            'producao_op': int(total_prod_op),
            'refugo_op_acumulado': int(total_waste_op),
            'toneladas_op': float(ton_op),
            'diferenca_op': int(dif_op),
            'producao_turno': int(total_turno),
            'toneladas_turno': float(ton_turno),
            'turno_atual_nome': turno_atual,
            
            # Métricas OEE
            'oee_realtime': float(oee),
            'performance_realtime': float(performance * 100),
            'quality_realtime': float(qualidade * 100),
            'availability_realtime': float(disponibilidade * 100),
            
            # NOVOS: Métricas temporais
            'tempo_planejado_segundos': int(tempo_planejado),
            'tempo_parado_segundos': int(tempo_parado),
            'tempo_produtivo_segundos': int(tempo_planejado - tempo_parado) if tempo_planejado > 0 else 0,
        }

# Singleton
engine = None
def get_engine(client, django_url):
    global engine
    if engine is None:
        engine = ProductionEngine(client, django_api_url=django_url)
    return engine