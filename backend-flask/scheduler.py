import logging
import time
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from decouple import config

# Import the diagnostic function
from services.diagnostics_engine import check_continuous_optimization

logger = logging.getLogger('Scheduler')
DJANGO_API_URL = config('DJANGO_API_URL', default='http://127.0.0.1:8000/api')

def job_shift_end_check():
    """
    Verifica se algum turno está terminando e força reset de contadores.
    Executa a cada minuto para detectar fim de turno com precisão.
    """
    logger.info("⏰ Verificando fim de turnos...")
    
    try:
        from datetime import datetime, timedelta
        
        # Busca turnos ativos do Django
        url = f"{DJANGO_API_URL}/turnos/?ativo=true"
        resp = requests.get(url, timeout=3)
        
        if not resp.ok:
            logger.error(f"Falha ao buscar turnos: {resp.status_code}")
            return
        
        data = resp.json()
        turnos = data.get('results', data) if isinstance(data, dict) else data
        
        now = datetime.now()
        now_time = now.time()
        
        for turno in turnos:
            try:
                hora_fim = datetime.strptime(turno['hora_fim'], '%H:%M:%S').time()
                
                # Calcula diferença em segundos até o fim do turno
                fim_dt = datetime.combine(now.date(), hora_fim)
                
                # Ajuste para turno noturno (virada de dia)
                hora_inicio = datetime.strptime(turno['hora_inicio'], '%H:%M:%S').time()
                if hora_inicio > hora_fim:
                    # Turno noturno
                    if now_time < hora_inicio:
                        # Estamos no dia seguinte, fim é hoje
                        pass
                    else:
                        # Estamos no mesmo dia, fim é amanhã
                        fim_dt += timedelta(days=1)
                
                diff = (fim_dt - now).total_seconds()
                
                # Se está nos últimos 60 segundos do turno, executa reset
                if 0 < diff <= 60:
                    logger.info(f"🔔 Turno {turno['nome']} terminando em {diff:.0f}s - Executando reset")
                    
                    # Chama endpoint de reset
                    reset_url = "http://localhost:5000/api/shift/reset"
                    reset_resp = requests.post(reset_url, json={}, timeout=5)
                    
                    if reset_resp.ok:
                        result = reset_resp.json()
                        logger.info(f"✓ Reset executado: {result.get('message')}")
                    else:
                        logger.error(f"Erro no reset: {reset_resp.status_code}")
                
                # Log de debug para turnos próximos (5 minutos)
                elif 0 < diff <= 300:
                    logger.debug(f"Turno {turno['nome']} termina em {diff/60:.1f} minutos")
            
            except Exception as e:
                logger.error(f"Erro processando turno {turno.get('nome', 'desconhecido')}: {e}")
    
    except Exception as e:
        logger.error(f"Erro no job de fim de turno: {e}")

def job_continuous_optimization():
    """
    Periodic job to check for Golden State optimization opportunities.
    """
    logger.info("⏰ Running Golden State Optimization Check...")
    
    try:
        # Fetch active equipments from Django
        url = f"{DJANGO_API_URL}/equipamentos/"
        resp = requests.get(url, timeout=5)
        
        if not resp.ok:
            logger.error(f"Failed to fetch equipments for optimization check: {resp.status_code}")
            return

        results = resp.json().get('results', [])
        
        count = 0
        optimized = 0
        
        for eq in results:
            eq_code = eq.get('codigo')
            # Only check active equipments usually, but assuming all returned are candidates
            if eq_code:
                count += 1
                # Run the check
                # Note: This runs in a thread, so influx client needs to be thread-safe or created inside
                # Since diagnostics_engine uses a global client, it should be fine for reads
                if check_continuous_optimization(eq_code):
                    optimized += 1
        
        logger.info(f"✅ Optimization Check Complete. Checked: {count}, Optimized: {optimized}")

    except Exception as e:
        logger.error(f"Error in Optimization Job: {e}")

def job_aggregate_line_metrics():
    """
    Calcula e persiste métricas consolidadas da linha (ex: Descarte Total, OLE Médio).
    Executa a cada 1 minuto.
    """
    try:
        from influx_data_provider import get_client as get_influx_client
        influx_client = current_app.extensions.get('influx_client')
        if not influx_client: return

        # 1. Totalizar Descarte e Produção de todos equipamentos
        # Query pega o último valor de acumuladores do turno
        query = "SELECT last(descarte) as descarte, last(contagem_saida) as producao, last(formato_gramas) as formato FROM production WHERE time > now() - 1h GROUP BY \"equipment\""
        rs = influx_client.query(query)
        
        total_descarte_tons = 0.0
        total_producao_pcs = 0.0
        total_descarte_pcs = 0.0
        
        for (name, tags), points in rs.items():
            if points:
                p = points[0]
                desc = float(p.get('descarte', 0) or 0)
                prod = float(p.get('producao', 0) or 0)
                fmt = float(p.get('formato', 0) or 0)
                
                # Descarte em Tons
                descarte_kg = (desc * fmt) / 1000.0
                total_descarte_tons += descarte_kg / 1000.0
                
                total_producao_pcs += prod
                total_descarte_pcs += desc
        
        # Percentual de Descarte da Linha
        perc_descarte = 0.0
        total_processado = total_producao_pcs + total_descarte_pcs
        if total_processado > 0:
            perc_descarte = (total_descarte_pcs / total_processado) * 100.0
            
        # Persistir em nova measurement 'line_metrics'
        points = [{
            "measurement": "line_metrics",
            "tags": {
                "line": "L01", # TODO: Tornar dinâmico se houver mais linhas
                "type": "waste_agg"
            },
            "fields": {
                "waste_tons": float(total_descarte_tons),
                "waste_percent": float(perc_descarte),
                "total_production_pcs": int(total_producao_pcs),
                "total_waste_pcs": int(total_descarte_pcs)
            },
            "time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        }]
        
        influx_client.write_points(points)
        # logger.info(f"📊 Descarte Agregado: {total_descarte_tons:.3f} t ({perc_descarte:.2f}%)")
        
    except Exception as e:
        logger.error(f"Erro job aggregate metrics: {e}")

def start_scheduler(app):
    """
    Starts the background scheduler.
    """
    try:
        scheduler = BackgroundScheduler()
        
        # Add job to run every 5 minutes
        # Job de reset de turno (1 minuto)
        scheduler.add_job(job_shift_end_check, 'interval', minutes=1, id='shift_end_check')
        
        scheduler.add_job(job_continuous_optimization, 'interval', minutes=5, id='golden_state_opt')
        
        # New "The Watcher" Jobs (Auto-Capture Triggers)
        from services.watcher import check_5min_triggers, check_30min_triggers, check_hourly_master, check_waste_backoff
        
        # 1. Performance & Efficiency (Now 1 min for better responsiveness)
        scheduler.add_job(check_5min_triggers, 'interval', minutes=1, args=[app], id='watcher_5m')
        
        # 2. Stability (30 min)
        scheduler.add_job(check_30min_triggers, 'interval', minutes=30, args=[app], id='watcher_30m')
        
        # 3. Golden Master (1 hour)
        scheduler.add_job(check_hourly_master, 'interval', minutes=60, args=[app], id='watcher_60m')
        
        # 4. Waste Backoff (1 min)
        scheduler.add_job(check_waste_backoff, 'interval', minutes=1, args=[app], id='watcher_waste')
        
        # 5. Agregação de Métricas da Linha (Descarte, etc)
        scheduler.add_job(job_aggregate_line_metrics, 'interval', minutes=1, id='line_metrics_agg')
        
        scheduler.start()
        logger.info("🚀 Scheduler Started (Golden State Optimization: 5 min)")
        
        # Register shutdown
        import atexit
        atexit.register(lambda: scheduler.shutdown())
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
