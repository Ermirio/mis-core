from django.utils import timezone
from datetime import datetime, timedelta
import pytz

def get_window(period, now=None):
    """
    Returns (start, end) for a given period ('shift', 'day', 'week', 'month')
    in America/Sao_Paulo timezone.
    """
    if now is None:
        now = timezone.localtime(timezone.now())
    
    # Ensure now is in the correct timezone
    tz = pytz.timezone('America/Sao_Paulo')
    if now.tzinfo is None:
        now = tz.localize(now)
    else:
        now = now.astimezone(tz)

    start_time = now
    end_time = now

    if period == 'shift':
        from .turno_helpers import obter_turno_atual, calcular_inicio_turno, calcular_fim_turno
        turno = obter_turno_atual()
        if turno:
            start_time = calcular_inicio_turno(turno)
            end_time = calcular_fim_turno(turno)
            # Handle midnight crossing logic is inside helpers, but let's ensure
            # If start > end, it means end is next day. 
            # But calcular_fim_turno usually returns datetime.
            # Let's trust helpers but verify if they return datetimes.
        else:
            # Fallback or error state handling should be in view
            return None, None

    elif period == 'day':
        start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    elif period == 'week':
        # Monday = 0
        start_of_week = now - timedelta(days=now.weekday())
        start_time = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_time + timedelta(days=6)
        end_time = end_of_week.replace(hour=23, minute=59, second=59, microsecond=999999)

    elif period == 'month':
        start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of month
        next_month = (start_time.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_time = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)

    return start_time, end_time

def calculate_time_metrics(start, end, now=None):
    """
    Calculates elapsed hours and remaining hours.
    elapsed_hours: max(epsilon, (now - start).total_seconds() / 3600)
    hours_remaining: max(0, (end - now).total_seconds() / 3600)
    """
    if now is None:
        now = timezone.localtime(timezone.now())
    
    tz = pytz.timezone('America/Sao_Paulo')
    if now.tzinfo is None:
        now = tz.localize(now)
    else:
        now = now.astimezone(tz)
        
    # Ensure start/end are comparable
    if start.tzinfo is None: start = tz.localize(start)
    else: start = start.astimezone(tz)
    
    if end.tzinfo is None: end = tz.localize(end)
    else: end = end.astimezone(tz)

    # Elapsed
    delta_elapsed = now - start
    elapsed_hours = max(1/60.0, delta_elapsed.total_seconds() / 3600.0) # Epsilon 1 min

    # Remaining
    delta_remaining = end - now
    hours_remaining = max(0.0, delta_remaining.total_seconds() / 3600.0)

    return elapsed_hours, hours_remaining
