from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import LinhaProducao

class LineAnalysisView(viewsets.ViewSet):
    """
    ViewSet para Análise Detalhada de Linha (Vazão Necessária, Projeção, etc.)
    Suporta granularidade: shift, day, week, month
    """
    
    @action(detail=True, methods=['get'])
    def analysis(self, request, pk=None):
        """
        GET /api/linhas/{id}/analysis?granularity=shift|day|week|month
        """
        granularity = request.query_params.get('granularity', 'shift')
        
        # 1. Resolve Line
        try:
            # pk can be ID or Code
            if pk.isdigit():
                linha = LinhaProducao.objects.get(pk=pk)
            else:
                linha = LinhaProducao.objects.get(codigo=pk)
        except LinhaProducao.DoesNotExist:
            return Response({'error': 'Linha não encontrada'}, status=status.HTTP_404_NOT_FOUND)
            
        # 2. Time Window
        from .utils import get_window, calculate_time_metrics
        from .turno_helpers import obter_turno_atual, calcular_inicio_turno
        from .influx_helpers import get_aggregated_metrics
        
        now = timezone.localtime(timezone.now())
        start_time, end_time = get_window(granularity, now)
        
        if not start_time or not end_time:
             return Response({
                'planned_production': 0, 'actual_production': 0, 'required_flow_rate': 0,
                'projected_production': 0, 'status': 'no_config'
            })
            
        elapsed_hours, hours_remaining = calculate_time_metrics(start_time, end_time, now)
        
        # 3. Fetch Metrics from InfluxDB
        # Determine period and timestamp
        periodo_influx = 'TURNO'
        timestamp_query = None
        
        if granularity == 'shift':
            periodo_influx = 'TURNO'
            turno_atual = obter_turno_atual()
            if turno_atual:
                timestamp_query = calcular_inicio_turno(turno_atual)
        elif granularity == 'day':
            periodo_influx = 'DIA'
            timestamp_query = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
        # Fetch Aggregated Metrics for the Line
        metrics = get_aggregated_metrics('linha', linha.codigo, periodo_influx, timestamp_query)
        
        planned_tons = 0.0
        actual_tons = 0.0
        
        if metrics:
            # Use the new 'meta_toneladas' field if available, otherwise fallback to 'meta' (which might be units)
            # But we know we just added 'meta_toneladas' to Agregador.
            # However, for old data, it might be missing.
            # If 'meta_toneladas' is missing, we might need to calculate it on the fly?
            # For now, let's assume it's there or 0.
            planned_tons = float(metrics.get('meta_toneladas', 0.0))
            
            # Fallback: if meta_toneladas is 0 but meta is > 0, maybe it's the old format?
            # But 'meta' is units. We can't easily convert without iterating all equipments.
            # So we rely on the new field.
            
            actual_tons = float(metrics.get('toneladas', 0.0))
            
        # 4. Calculations
        saldo = planned_tons - actual_tons
        required_flow_rate = 0.0
        
        if saldo <= 0:
            required_flow_rate = 0.0
        elif hours_remaining == 0:
            required_flow_rate = None # Impossible
        else:
            required_flow_rate = saldo / hours_remaining
            
        # Projection
        current_rate = actual_tons / elapsed_hours if elapsed_hours > 0 else 0
        projected_production = actual_tons + (current_rate * hours_remaining)
        
        return Response({
            'line_code': linha.codigo,
            'granularity': granularity,
            'planned_production': round(planned_tons, 2),
            'actual_production': round(actual_tons, 2),
            'required_flow_rate': round(required_flow_rate, 2) if required_flow_rate is not None else None,
            'projected_production': round(projected_production, 2),
            'current_flow_rate': round(current_rate, 2),
            'hours_remaining': round(hours_remaining, 2),
            'window': {
                'from': start_time.isoformat(),
                'to': end_time.isoformat()
            }
        })
