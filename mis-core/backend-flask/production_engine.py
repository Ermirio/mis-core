import logging
import requests
import time
from datetime import datetime, timedelta

from oee_formula import OEEInputs, compute_oee

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
    
    def reset_shift_counters(self, equipment_code=None):
        """
        Reseta contadores de turno para um equipamento específico ou todos.
        Chamado pelo scheduler no fim do turno.
        """
        if equipment_code:
            # Reset de equipamento específico
            if equipment_code in self._cache:
                state = self._cache[equipment_code]
                state['acc_shift'] = 0
                state['acc_time_stop_shift'] = 0.0
                state['shift_start_time'] = None
                logger.info(f"✓ Reset de turno para {equipment_code}")
                return True
            return False
        else:
            # Reset de todos equipamentos
            count = 0
            for eq_code in list(self._cache.keys()):
                state = self._cache[eq_code]
                state['acc_shift'] = 0
                state['acc_time_stop_shift'] = 0.0
                state['shift_start_time'] = None
                count += 1
            logger.info(f"✓ Reset de turno para {count} equipamentos")
            return count > 0

    def get_state(self, equipment_code):
        return self._get_state(equipment_code)

    def _get_state(self, equipment_code):
        if equipment_code not in self._cache:
            self._cache[equipment_code] = {
                # Acumuladores de produção
                'last_raw': None,
                'last_raw_input': None, # Counter de Entrada
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
                
                raw_in_val = d.get('contagem_entrada')
                if raw_in_val is not None: state['last_raw_input'] = int(raw_in_val)
                
                waste_val = d.get('descarte')
                if waste_val is not None: state['last_waste'] = int(waste_val)
                
                # NOVO: Recupera timestamp e estado
                timestamp_val = d.get('timestamp_medicao')
                
                # NOVO: Recupera shift_start_time do banco
                shift_start_val = d.get('turno_inicio_timestamp')
                if shift_start_val: state['shift_start_time'] = float(shift_start_val)
                if timestamp_val: state['last_timestamp'] = float(timestamp_val)
                
                estado_val = d.get('estado_maquina')
                if estado_val is not None: state['last_estado'] = int(estado_val)
                
                state['op_code'] = current_op
                state['shift_code'] = current_shift
            
            state['initialized'] = True
        except Exception as e:
            logger.error(f"Erro load state: {e}")
            state['initialized'] = True

    def processar_dados(self, equipamento, op_atual, contagem_bruta, descarte, formato_gramas, planejado, velocidade_atual, estado_maquina, extra_context=None, contagem_entrada=0):
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
        # [BUG-7 FIX] outage longo (coletor caiu, servidor reiniciado, etc.)
        # NÃO pode "sumir" da Availability. Antes: time_delta>300s era zerado
        # e nada se acumulava em acc_time_stop_shift. Resultado: Availability
        # inflava artificialmente porque o tempo planejado seguia avançando
        # (now - shift_start) mas o tempo parado não cobria o gap. Decisão:
        #   - delta válido (1..MAX_TIME_DELTA): usa normal.
        #   - delta longo mas razoável (até OUTAGE_AS_DOWNTIME=2h): contabiliza
        #     COMO PARADO (worst-case operacional — mais honesto que esconder).
        #   - delta>OUTAGE_AS_DOWNTIME ou negativo: descarta (clock skew real).
        OUTAGE_AS_DOWNTIME_S = 7200  # 2h: limite acima do qual viramos hands-up
        time_delta = 0.0
        gap_outage = 0.0
        if state['last_timestamp'] is not None:
            raw_delta = now_timestamp - state['last_timestamp']
            if 0 < raw_delta <= self.MAX_TIME_DELTA:
                time_delta = raw_delta
            elif self.MAX_TIME_DELTA < raw_delta <= OUTAGE_AS_DOWNTIME_S:
                # Outage moderado — contabilizamos como parada não-planejada.
                logger.warning(
                    f"{equipamento}: outage de {raw_delta:.0f}s contabilizado como parada"
                )
                gap_outage = raw_delta
            else:
                # Clock skew, restart muito longo, ou time_delta negativo.
                logger.warning(
                    f"{equipamento}: delta tempo anormal ({raw_delta:.1f}s), descartado"
                )

        # 5. Acumula Tempo Parado
        # 5a. Estado != RUNNING durante a janela normal -> conta como parado.
        if state['last_estado'] is not None and time_delta > 0:
            if state['last_estado'] != 1:  # 1 = Produzindo
                state['acc_time_stop_shift'] += time_delta
        # 5b. Outage moderado -> conta como parado integralmente (BUG-7).
        if gap_outage > 0:
            state['acc_time_stop_shift'] += gap_outage
        
        # Atualiza referências temporais
        state['last_timestamp'] = now_timestamp
        state['last_estado'] = estado_maquina

        # 6. Deltas de Produção com Detecção Inteligente de Reset e MASS BALANCE
        # --- DELTA PRODUCTION (SAÍDA) ---
        if state['last_raw'] is not None:
            delta = contagem_bruta - state['last_raw']
            
            # Detecção de Reset Físico do Sensor
            if delta < 0:
                logger.info(f"{equipamento}: Reset físico detectado (contador diminuiu: {state['last_raw']} -> {contagem_bruta})")
                delta = contagem_bruta  # Usa valor atual como delta
            
            # Reset Lógico (Turno)
            elif shift_changed and delta > 1000:
                delta = 0
            
            delta = max(0, delta)
        else:
            # Primeira medição após restart:
            # NÃO calcula delta (assume que o que passou, passou), apenas sincroniza o last_raw
            # Isso evita que o primeiro pacote gere um pico falso ou zero indevido.
            if contagem_bruta > 0:
                 logger.info(f"{equipamento}: Sincronizando contador inicial: {contagem_bruta}")
            delta = 0
            # Se fosse necessário recuperar "o que perdeu enquanto estava off", precisaríamos do last_raw salvo no DB.
            # O _load_state_from_db já tentou recuperar. Se ainda é None, é porque não tem histórico ou falhou.
        
        state['last_raw'] = contagem_bruta

        # --- DELTA INPUT (ENTRADA) ---
        delta_input = 0
        if state['last_raw_input'] is not None:
            delta_input = contagem_entrada - state['last_raw_input']
            if delta_input < 0: # Reset
                delta_input = contagem_entrada
            elif shift_changed and delta_input > 1000:
                delta_input = 0
            delta_input = max(0, delta_input)
        else:
            # Init Check
            if contagem_entrada > 0:
                 logger.info(f"{equipamento}: Sincronizando contador entrada inicial: {contagem_entrada}")
            delta_input = 0
        
        state['last_raw_input'] = contagem_entrada

        # --- WASTE CALCULATION (MASS BALANCE) ---
        # Waste = (Input - Output)
        # We calculate delta_waste based on deltas
        
        delta_waste_calc = delta_input - delta
        
        # DEBUG LOGGING (Optional - too verbose?)
        # if delta_input > 0 or delta > 0:
        #    logger.debug(f"{equipamento} Mass Balance: In={delta_input}, Out={delta}, Waste={delta_waste_calc}")

        # Accumulate Waste
        # Allows negative delta_waste (buffer clearing) but keeps total accumulated waste >= 0
        state['acc_waste_op'] += delta_waste_calc
        if state['acc_waste_op'] < 0:
            state['acc_waste_op'] = 0 # Cannot have negative total waste

        # 7. Acumuladores de Produção
        if delta > 0:
            state['acc_op'] += delta
            # Verifica se turno é válido para acumular
            if turno_atual not in ["Sem Turno Configurado", "Fora de Turno", "N/A"]:
                state['acc_shift'] += delta
            else:
                pass # Ignora acumulação fora de turno
        
        # 8. CÁLCULO DE OEE — agora delegado a compute_oee (ISO 22400-2 SSOT).
        # [BUG-3 + INC-2 FIX] antes Performance era avg(velocidade)/nominal —
        # ignorava tempo produtivo e era ruído quando velocidade=0 transitória
        # entrava no buffer. Agora usamos a fórmula correta:
        #     Performance = (Total Count × Ideal Cycle Time) / Actual Production Time
        # E todo o cálculo (A, P, Q, OEE) passa pelo MESMO compute_oee que o
        # FastAPI usa, garantindo consistência entre /api/v1 e /api/v2.

        # ---- Tempo planejado / parado / produtivo ----
        tempo_planejado = 0.0
        tempo_parado = state['acc_time_stop_shift']
        if turno_info and state['shift_start_time']:
            tempo_planejado = max(0.0, now_timestamp - state['shift_start_time'])
        tempo_produtivo = max(0.0, tempo_planejado - tempo_parado)

        # ---- INPUT total (good + reject) — base do Total Count ISO ----
        total_prod_op  = state['acc_op']             # OUTPUT (good count)
        total_waste_op = state['acc_waste_op']       # REJECT
        total_input_op = total_prod_op + total_waste_op   # INPUT = total count

        # ---- Ideal cycle time ----
        # Vel nominal está em unidades/minuto. Ideal cycle = 60s / vel_nominal.
        # Guard: se vel_nominal vier 0/None, fallback para 1s/un (não estourar div/0).
        ideal_cycle_s = (60.0 / vel_nominal) if vel_nominal and vel_nominal > 0 else 1.0

        # ---- Caso edge: turno acabou de começar (planejado<1s) ou sem turno ----
        if tempo_planejado <= 0 or tempo_produtivo <= 0:
            # Sem janela suficiente para a fórmula temporal — usar fallback
            # baseado no estado instantâneo (mantém compat com versão antiga).
            disponibilidade = 1.0 if estado_maquina == 1 else 0.0
            performance = 0.0
            performance_raw = 0.0
            quality_valid = total_input_op > 0
            qualidade = (total_prod_op / total_input_op) if quality_valid else 1.0
            oee_valid = quality_valid
            oee_frac = (disponibilidade * performance * qualidade) if oee_valid else 0.0
        else:
            r = compute_oee(OEEInputs(
                actual_production_time_s=tempo_produtivo,
                planned_production_time_s=tempo_planejado,
                total_count=total_input_op,
                good_count=total_prod_op,
                ideal_cycle_time_s=ideal_cycle_s,
            ))
            disponibilidade = r.availability
            performance     = r.performance        # cap 1.0 (ISO) — já fica em fração
            performance_raw = r.performance_raw    # cap 1.05 — para display
            qualidade       = r.quality
            quality_valid   = r.quality_valid
            oee_valid       = r.oee_valid
            oee_frac        = r.oee

        # OEE no formato "percentual 0..100" — manter contrato antigo dos consumers.
        oee = oee_frac * 100.0
        
        # 9. Totais
        ton_op = (total_prod_op * formato_gramas) / 1_000_000.0 if formato_gramas else 0
        dif_op = total_prod_op - planejado
        
        total_turno = state['acc_shift']
        ton_turno = (total_turno * formato_gramas) / 1_000_000.0 if formato_gramas else 0
        
        metrics = {
            'producao_op': int(total_prod_op),
            'refugo_op_acumulado': int(total_waste_op),
            'toneladas_op': float(ton_op),
            'diferenca_op': int(dif_op),
            'producao_turno': int(total_turno),
            'toneladas_turno': float(ton_turno),
            'turno_atual_nome': turno_atual,

            # Metricas OEE - todas em escala 0..100 para o frontend legado.
            'oee_realtime': float(oee),
            'performance_realtime': float(performance_raw * 100),
            'quality_realtime': float(qualidade * 100),
            'availability_realtime': float(disponibilidade * 100),
            'quality_valid': bool(quality_valid),
            'oee_valid': bool(oee_valid),
            'planejado_op': int(planejado),

            # Metricas temporais
            'tempo_planejado_segundos': int(tempo_planejado),
            'tempo_parado_segundos': int(tempo_parado),
            'tempo_produtivo_segundos': int(tempo_planejado - tempo_parado) if tempo_planejado > 0 else 0,

            # Dados para calculo de vazao
            'velocidade_atual': int(velocidade_atual),
            'formato_gramas': int(formato_gramas),
        }

        state['latest_metrics'] = metrics

        # Persistencia de Contexto Rico (SKU, Descricao, CUC)
        if extra_context:
            state['last_payload'] = extra_context

        # turno_inicio_timestamp para persistencia
        if state['shift_start_time']:
            metrics['turno_inicio_timestamp'] = float(state['shift_start_time'])

        return metrics

# Singleton
engine = None
def get_engine(client, django_url):
    global engine
    if engine is None:
        engine = ProductionEngine(client, django_api_url=django_url)
    return engine
