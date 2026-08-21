from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging

logger = logging.getLogger('DiagnosticRules')

class DiagnosticRule(ABC):
    @abstractmethod
    def evaluate(self, equipamento_codigo, realtime_data, history_data, golden_state):
        """
        Evaluates the rule and returns a DiagnosticAlert or None.
        """
        pass

class DiagnosticAlert:
    def __init__(self, rule_name, severity, message, details=None):
        self.rule_name = rule_name
        self.severity = severity  # 'info', 'warning', 'critical'
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()

class MicroStopsRule(DiagnosticRule):
    def __init__(self, window_minutes=60, max_stops=4):
        self.window_minutes = window_minutes
        self.max_stops = max_stops

    def evaluate(self, equipamento_codigo, realtime_data, history_data, golden_state):
        # Filter history for 'PARADO' states in the last window_minutes
        # Assuming history_data is a list of events: {'estado': 'PARADO', 'inicio': ..., 'fim': ..., 'duracao': ...}
        
        if not history_data:
            return None

        stops = [
            e for e in history_data 
            if e.get('estado') in ['PARADO', 'FALTA_MAT', 'MANUTENCAO'] 
            and e.get('duracao_segundos', 0) < 60 # Micro-stop definition: < 1 min
        ]

        if len(stops) >= self.max_stops:
            return DiagnosticAlert(
                rule_name="MicroStops",
                severity="warning",
                message=f"{len(stops)} micro-paradas detectadas nos últimos {self.window_minutes} min.",
                details={'stops_count': len(stops), 'threshold': self.max_stops}
            )
        return None

class StarvationRule(DiagnosticRule):
    def __init__(self, threshold_minutes=10):
        self.threshold_minutes = threshold_minutes

    def evaluate(self, equipamento_codigo, realtime_data, history_data, golden_state):
        # Check if current state is WAIT_PREV or BLOCK_NEXT for too long
        current_state = realtime_data.get('medicoes', {}).get('estado')
        # We need the duration of the current state. 
        # Assuming realtime_data might have 'last_state_change' or we infer from history.
        # For now, let's look at the most recent history event if it matches current state and is open (fim=None)
        
        if not history_data:
            return None

        # Sort history by start time descending
        latest_event = history_data[0] # Assuming sorted
        
        if latest_event.get('estado') in ['WAIT_PREV', 'BLOCK_NEXT']:
            # Calculate duration
            # Calculate duration
            # InfluxDB 1.8 returns ISO format like '2023-10-27T10:00:00Z'
            try:
                start_time = datetime.fromisoformat(latest_event['inicio'].replace('Z', '+00:00'))
            except ValueError:
                 # Fallback for other formats if needed
                 start_time = datetime.strptime(latest_event['inicio'], "%Y-%m-%dT%H:%M:%SZ")
            
            duration_min = (datetime.utcnow() - start_time.replace(tzinfo=None)).total_seconds() / 60
            
            if duration_min > self.threshold_minutes:
                state_name = "Aguardando Anterior" if latest_event['estado'] == 'WAIT_PREV' else "Bloqueado pelo Próximo"
                return DiagnosticAlert(
                    rule_name="StarvationBlockage",
                    severity="warning",
                    message=f"Equipamento {state_name} por {int(duration_min)} min.",
                    details={'state': latest_event['estado'], 'duration_min': duration_min}
                )
        return None

class GoldenStateDeviationRule(DiagnosticRule):
    def __init__(self, metric='velocidade_atual', threshold_percent=15):
        self.metric = metric
        self.threshold_percent = threshold_percent

    def evaluate(self, equipamento_codigo, realtime_data, history_data, golden_state):
        if not golden_state:
            return None

        target_value = golden_state.get(self.metric)
        current_value = realtime_data.get('medicoes', {}).get(self.metric)

        if target_value is None or current_value is None:
            return None
            
        if target_value == 0: 
            return None

        deviation = abs(target_value - current_value) / target_value * 100
        
        if deviation > self.threshold_percent:
            # Only alert if it's a negative deviation (performance drop) for velocity
            if self.metric == 'velocidade_atual' and current_value < target_value:
                 return DiagnosticAlert(
                    rule_name="GoldenStateDeviation",
                    severity="warning",
                    message=f"Velocidade {int(deviation)}% abaixo do Golden State ({current_value} vs {target_value}).",
                    details={'metric': self.metric, 'current': current_value, 'target': target_value, 'deviation': deviation}
                )
            # For other metrics, maybe bidirectional deviation is bad?
            
        return None
