# backend/src/routes/analytics_dashboard.py
from flask import Blueprint, request, jsonify
import logging
from datetime import datetime, timedelta
import random
import math

logger = logging.getLogger(__name__)
analytics_dashboard_bp = Blueprint('analytics_dashboard', __name__)

# Custo médio por kWh em R$
COST_PER_KWH = 0.85

# Tipos de energia e suas proporções típicas
ENERGY_TYPES = {
    'electricity': {'name': 'Eletricidade', 'color': '#3B82F6', 'percentage': 65},
    'steam': {'name': 'Vapor', 'color': '#F59E0B', 'percentage': 20},
    'biomass': {'name': 'Biomassa', 'color': '#10B981', 'percentage': 10},
    'natural_gas': {'name': 'Gás Natural', 'color': '#8B5CF6', 'percentage': 5}
}

@analytics_dashboard_bp.route('/analytics/dashboard-summary', methods=['GET'])
def get_dashboard_summary():
    """Retorna resumo do dashboard com consumo, custo e comparativos"""
    try:
        # Parâmetros de filtro
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        shift = request.args.get('shift')  # morning, afternoon, night
        line_id = request.args.get('line_id', type=int)
        
        # Período default: últimos 7 dias
        if not end_date:
            end_date = datetime.now()
        else:
            end_date = datetime.fromisoformat(end_date)
            
        if not start_date:
            start_date = end_date - timedelta(days=7)
        else:
            start_date = datetime.fromisoformat(start_date)
        
        days = (end_date - start_date).days or 1
        
        # Simular consumo baseado em padrões industriais
        base_consumption = 15000  # kWh/dia base
        
        # Adicionar variação por turno
        shift_multipliers = {'morning': 1.2, 'afternoon': 1.0, 'night': 0.8}
        shift_mult = shift_multipliers.get(shift, 1.0)
        
        # Consumo atual (período selecionado)
        current_consumption = base_consumption * days * shift_mult
        current_consumption += random.uniform(-0.1, 0.1) * current_consumption
        current_consumption = round(current_consumption, 2)
        
        # Custo atual
        current_cost = round(current_consumption * COST_PER_KWH, 2)
        
        # Período anterior (mesmo intervalo)
        previous_consumption = base_consumption * days * shift_mult
        previous_consumption += random.uniform(-0.15, 0.05) * previous_consumption  # Tendência de melhoria
        previous_consumption = round(previous_consumption, 2)
        previous_cost = round(previous_consumption * COST_PER_KWH, 2)
        
        # Calcular variação percentual
        consumption_delta = round(((current_consumption - previous_consumption) / previous_consumption) * 100, 1) if previous_consumption else 0
        cost_delta = round(((current_cost - previous_cost) / previous_cost) * 100, 1) if previous_cost else 0
        
        # Eficiência (kWh/ton produzido) - simulado
        current_efficiency = round(random.uniform(45, 55), 1)
        previous_efficiency = round(random.uniform(48, 58), 1)
        efficiency_delta = round(((current_efficiency - previous_efficiency) / previous_efficiency) * 100, 1)
        
        # Tendência geral
        trend = 'down' if consumption_delta < 0 else 'up' if consumption_delta > 0 else 'stable'
        
        return jsonify({
            'success': True,
            'data': {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                    'days': days
                },
                'current': {
                    'consumption_kwh': current_consumption,
                    'cost_brl': current_cost,
                    'efficiency_kwh_ton': current_efficiency
                },
                'previous': {
                    'consumption_kwh': previous_consumption,
                    'cost_brl': previous_cost,
                    'efficiency_kwh_ton': previous_efficiency
                },
                'delta': {
                    'consumption_percent': consumption_delta,
                    'cost_percent': cost_delta,
                    'efficiency_percent': efficiency_delta
                },
                'trend': trend
            }
        })
        
    except Exception as e:
        logger.error(f"Erro em dashboard-summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_dashboard_bp.route('/analytics/time-series', methods=['GET'])
def get_time_series():
    """Retorna série temporal de consumo e custo"""
    try:
        period = request.args.get('period', 'hourly')  # hourly, daily, weekly
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        now = datetime.now()
        
        # Determinar intervalo baseado no período
        if period == 'hourly':
            points = 24
            delta = timedelta(hours=1)
            start = now - timedelta(hours=24)
            format_str = '%H:%M'
        elif period == 'daily':
            points = 30
            delta = timedelta(days=1)
            start = now - timedelta(days=30)
            format_str = '%d/%m'
        else:  # weekly
            points = 12
            delta = timedelta(weeks=1)
            start = now - timedelta(weeks=12)
            format_str = 'Sem %W'
        
        data = []
        current_time = start
        
        for i in range(points):
            # Padrão de consumo baseado na hora/dia
            if period == 'hourly':
                hour = current_time.hour
                if 6 <= hour <= 18:  # Horário comercial
                    base = 1200
                elif 19 <= hour <= 22:  # Pico
                    base = 1500
                else:  # Madrugada
                    base = 600
            else:
                # Variação semanal (menos consumo no fim de semana)
                day_of_week = current_time.weekday()
                if day_of_week >= 5:  # Weekend
                    base = 800
                else:
                    base = 1200
            
            # Adicionar variação aleatória
            consumption = round(base * random.uniform(0.85, 1.15), 2)
            cost = round(consumption * COST_PER_KWH, 2)
            
            data.append({
                'timestamp': current_time.isoformat(),
                'label': current_time.strftime(format_str),
                'consumption_kwh': consumption,
                'cost_brl': cost
            })
            
            current_time += delta
        
        return jsonify({
            'success': True,
            'data': data,
            'period': period,
            'unit_cost': COST_PER_KWH
        })
        
    except Exception as e:
        logger.error(f"Erro em time-series: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_dashboard_bp.route('/analytics/energy-breakdown', methods=['GET'])
def get_energy_breakdown():
    """Retorna breakdown de energia por tipo"""
    try:
        # Simular valores baseados nas proporções definidas
        total_consumption = random.uniform(80000, 120000)
        
        breakdown = []
        for key, info in ENERGY_TYPES.items():
            # Adicionar pequena variação nas proporções
            percentage = info['percentage'] + random.uniform(-2, 2)
            value = round(total_consumption * (percentage / 100), 2)
            cost = round(value * COST_PER_KWH, 2)
            
            breakdown.append({
                'type': key,
                'name': info['name'],
                'color': info['color'],
                'value_kwh': value,
                'cost_brl': cost,
                'percentage': round(percentage, 1)
            })
        
        # Normalizar percentuais para somar 100%
        total_pct = sum(item['percentage'] for item in breakdown)
        for item in breakdown:
            item['percentage'] = round((item['percentage'] / total_pct) * 100, 1)
        
        return jsonify({
            'success': True,
            'data': breakdown,
            'total_kwh': round(total_consumption, 2),
            'total_cost': round(total_consumption * COST_PER_KWH, 2)
        })
        
    except Exception as e:
        logger.error(f"Erro em energy-breakdown: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_dashboard_bp.route('/analytics/heatmap', methods=['GET'])
def get_heatmap():
    """Retorna dados de heatmap (consumo por dia da semana x hora)"""
    try:
        days = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb']
        
        heatmap_data = []
        max_value = 0
        min_value = float('inf')
        
        for day_idx, day_name in enumerate(days):
            for hour in range(24):
                # Padrão de consumo
                is_weekend = day_idx == 0 or day_idx == 6
                is_business_hours = 6 <= hour <= 18
                is_peak = 19 <= hour <= 22
                
                if is_weekend:
                    base = 400  # Fim de semana = baixo
                elif is_peak:
                    base = 1400  # Pico noturno
                elif is_business_hours:
                    base = 1100  # Horário comercial
                else:
                    base = 500  # Madrugada
                
                value = round(base * random.uniform(0.9, 1.1), 0)
                max_value = max(max_value, value)
                min_value = min(min_value, value)
                
                heatmap_data.append({
                    'day': day_name,
                    'day_index': day_idx,
                    'hour': hour,
                    'hour_label': f'{hour:02d}:00',
                    'value': value
                })
        
        return jsonify({
            'success': True,
            'data': heatmap_data,
            'days': days,
            'hours': list(range(24)),
            'range': {
                'min': min_value,
                'max': max_value
            }
        })
        
    except Exception as e:
        logger.error(f"Erro em heatmap: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_dashboard_bp.route('/analytics/insights', methods=['GET'])
def get_insights():
    """Retorna insights em linguagem natural sobre o consumo"""
    try:
        period = request.args.get('period', 'week')  # week, month
        
        # Simular dados de comparação
        consumption_change = random.uniform(-15, 15)
        cost_change = random.uniform(-12, 18)
        peak_hour = random.choice([19, 20, 21])
        peak_day = random.choice(['segunda', 'terça', 'quarta'])
        
        insights = []
        
        # Insight de consumo
        if consumption_change > 0:
            insights.append({
                'type': 'warning',
                'icon': 'trending-up',
                'title': 'Consumo Aumentou',
                'description': f'O consumo de energia aumentou {abs(consumption_change):.1f}% em relação ao período anterior.',
                'recommendation': 'Verifique equipamentos com maior demanda e considere otimização.'
            })
        else:
            insights.append({
                'type': 'success',
                'icon': 'trending-down',
                'title': 'Consumo Reduzido',
                'description': f'Excelente! O consumo diminuiu {abs(consumption_change):.1f}% comparado ao período anterior.',
                'recommendation': 'Continue monitorando para manter a eficiência.'
            })
        
        # Insight de horário de pico
        insights.append({
            'type': 'info',
            'icon': 'clock',
            'title': 'Horário de Pico',
            'description': f'O maior consumo ocorre às {peak_hour}h, concentrado na {peak_day}-feira.',
            'recommendation': 'Considere redistribuir cargas para horários de menor tarifa.'
        })
        
        # Insight de custo
        if cost_change > 10:
            insights.append({
                'type': 'alert',
                'icon': 'dollar-sign',
                'title': 'Custo Elevado',
                'description': f'Os custos de energia aumentaram {cost_change:.1f}% este período.',
                'recommendation': 'Revise contratos de fornecimento e eficiência de equipamentos.'
            })
        
        # Insight de eficiência
        efficiency_score = random.randint(70, 95)
        insights.append({
            'type': 'info' if efficiency_score >= 80 else 'warning',
            'icon': 'zap',
            'title': f'Score de Eficiência: {efficiency_score}%',
            'description': f'Sua planta está operando com eficiência {"boa" if efficiency_score >= 80 else "abaixo do ideal"}.',
            'recommendation': 'Monitore motores e sistemas de ar comprimido para ganhos adicionais.' if efficiency_score < 80 else 'Mantenha as práticas atuais de gestão energética.'
        })
        
        return jsonify({
            'success': True,
            'data': insights,
            'generated_at': datetime.now().isoformat(),
            'period': period
        })
        
    except Exception as e:
        logger.error(f"Erro em insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@analytics_dashboard_bp.route('/analytics/export-csv', methods=['GET'])
def export_csv():
    """Exporta dados como CSV"""
    try:
        data_type = request.args.get('type', 'time-series')
        
        # Gerar dados baseado no tipo
        if data_type == 'time-series':
            # Reutilizar lógica do time-series
            now = datetime.now()
            points = 24
            delta = timedelta(hours=1)
            start = now - timedelta(hours=24)
            
            csv_lines = ['Timestamp,Consumo (kWh),Custo (R$)']
            current_time = start
            
            for i in range(points):
                hour = current_time.hour
                if 6 <= hour <= 18:
                    base = 1200
                elif 19 <= hour <= 22:
                    base = 1500
                else:
                    base = 600
                
                consumption = round(base * random.uniform(0.85, 1.15), 2)
                cost = round(consumption * COST_PER_KWH, 2)
                
                csv_lines.append(f'{current_time.isoformat()},{consumption},{cost}')
                current_time += delta
            
            csv_content = '\n'.join(csv_lines)
            
            return csv_content, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename=energy_data_{now.strftime("%Y%m%d_%H%M%S")}.csv'
            }
        
        return jsonify({'success': False, 'error': 'Tipo de exportação inválido'}), 400
        
    except Exception as e:
        logger.error(f"Erro em export-csv: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
