import logging
import time
import requests
from decouple import config
from influxdb import InfluxDBClient

# Configuração de Log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
INFLUXDB_HOST = config('INFLUXDB_HOST', default='influxdb')
INFLUXDB_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUXDB_USER = config('INFLUXDB_USER', default='admin')
INFLUXDB_PASSWORD = config('INFLUXDB_USER_PASSWORD', default='admin')
INFLUXDB_DATABASE = config('INFLUXDB_DATABASE', default='industrial_db')

DJANGO_API_URL = config('DJANGO_API_URL', default='http://backend-django:8000/api')

def get_influx_client():
    return InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USER, password=INFLUXDB_PASSWORD, database=INFLUXDB_DATABASE)

def get_factory_kpis(period=None):
    """
    Retorna KPIs consolidados da fábrica.
    Abordagem Híbrida:
    - Vazão/Produção: Django (Fonte da Verdade para totais)
    - OEE/Status: InfluxDB (Tempo real para Ranking e Cores)
    """
    try:
        # Mapping: Django Name -> Canonical Code (Layout Key)
        name_map = {
            'Linha 01': 'L01', 'Linha 02': 'L02', 'Linha 03': 'L03', 'Linha 04': 'L04',
            'Linha 05': 'L05', 'Linha 06': 'L06', 'Linha 07': 'L07', 'Linha 08': 'L08',
            'Linha 09': 'L09', 'Linha 10': 'L10', 'Linha 11': 'L11', 'Linha 12': 'L12',
            'Linha 13': 'L13', 'Linha 14': 'L14', 'Linha 15': 'L15', 'Linha 16': 'L16',
            'Linha 17': 'L17', 'Linha 18': 'L18', 'Linha 19': 'L19', 'Linha 20': 'L20',
            'Linha 20_B': 'L20_B'
        }

        # 1. Fetch Flow/Production/Planned/Required from Django
        django_metrics = {}
        factory_totals = {
            'producao_planejada_t': 0.0,
            'vazao_necessaria_tph': 0.0
        }
        
        try:
            # New: Fetch Factory Totals (Throughput)
            granularity_map = {'turno': 'shift', 'dia': 'day', 'semana': 'week', 'mes': 'month'}
            granularity = granularity_map.get(period, 'shift')
            
            resp_prod = requests.get(f"{DJANGO_API_URL}/production/window/throughput?granularity={granularity}", timeout=3)
            if resp_prod.status_code == 200:
                data_prod = resp_prod.json()
                factory_totals['producao_planejada_t'] = float(data_prod.get('planned_tons', 0))
                factory_totals['vazao_necessaria_tph'] = float(data_prod.get('min_required_tph') or 0)

            # Existing: Fetch Line Metrics
            resp = requests.get(f"{DJANGO_API_URL}/metricas_fabrica_consolidadas/", timeout=3)
            if resp.status_code == 200:
                for line in resp.json():
                    raw_name = line.get('linha_nome') or line.get('linha_codigo')
                    canonical_name = name_map.get(raw_name, raw_name)
                    django_metrics[canonical_name] = {
                        'vazao': float(line.get('vazao_real_ton_hora') or 0),
                        'producao': float(line.get('toneladas_produzidas') or 0)
                    }
        except Exception as e:
            logger.error(f"Error fetching Django metrics: {e}")

        # 2. Fetch OEE/Status from InfluxDB (Legacy Source - Working)
        client = get_influx_client()
        # Query last OEE and Status for all equipments (to calculate Line OLE)
        query = """
            SELECT last("oee_realtime") as oee, last("estado_maquina") as status
            FROM "production"
            WHERE time > now() - 10m
            GROUP BY "line", "equipment"
        """
        influx_data = {}
        try:
            rs = client.query(query)
            # Temporary dict to hold list of OEEs per line
            line_stats = {} 
            
            for (name, tags), points in rs.items():
                line_name = tags.get('line')
                if not line_name: continue
                
                points_list = list(points)
                if points_list:
                    p = points_list[0]
                    oee = float(p.get('oee', 0) or 0)
                    status = int(p.get('status', 2))
                    
                    if line_name not in line_stats:
                        line_stats[line_name] = {'oees': [], 'statuses': []}
                    
                    line_stats[line_name]['oees'].append(oee)
                    line_stats[line_name]['statuses'].append(status)

            # Calculate OLE (Average OEE) and Composite Status per Line
            for line_name, stats in line_stats.items():
                oees = stats['oees']
                statuses = stats['statuses']
                
                # OLE = Average of Equipment OEEs (Simple average for now)
                # Filter out 0s? Usually OLE includes all machines. 
                # If a machine is off (OEE 0), it pulls down the line OLE. Correct.
                avg_oee = sum(oees) / len(oees) if oees else 0.0
                
                # Status: If ANY machine is running (1), we consider line "Active" 
                # OR maybe if the majority? Let's use ANY for now to be optimistic, 
                # or check if Flow > 0 later.
                # Actually, let's use the most frequent status or priority to 1.
                composite_status = 1 if 1 in statuses else 2
                
                influx_data[line_name] = {
                    'oee': avg_oee,
                    'status': composite_status
                }
                
        except Exception as e:
            logger.error(f"Error fetching Influx metrics: {e}")

        # Layout Config (Full Original)
        layout_config = {
            "L20": {"area": "PREPARO", "pos_x": 0, "pos_y": 0, "w": 2, "h": 1, "critico": False},
            "L15": {"area": "PREPARO", "pos_x": 0, "pos_y": 1.2, "w": 2, "h": 1, "critico": False},
            "L19": {"area": "PREPARO", "pos_x": 0, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
            "L20_B": {"area": "PREPARO", "pos_x": 1.6, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
            "L16": {"area": "MISTURA", "pos_x": 3.5, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
            "L06": {"area": "ENVASE PÓS", "pos_x": 4.8, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
            "L18": {"area": "MISTURA", "pos_x": 6, "pos_y": 1.5, "w": 2, "h": 0.8, "critico": False},
            "L17": {"area": "MISTURA", "pos_x": 6, "pos_y": 2.5, "w": 2, "h": 1.2, "critico": False},
            "L10": {"area": "EMBALAGEM", "pos_x": 8.5, "pos_y": 0, "w": 1, "h": 4, "critico": True},
            "L02": {"area": "MISTURA", "pos_x": 9.8, "pos_y": 0, "w": 1, "h": 4, "critico": True},
            "L01": {"area": "ENVASE LÍQ", "pos_x": 11.1, "pos_y": 0, "w": 1, "h": 4, "critico": False},
            "L09": {"area": "ENVASE", "pos_x": 12.4, "pos_y": 0, "w": 1, "h": 4, "critico": False}
        }

        # 3. Merge Data
        all_lines = set(django_metrics.keys()) | set(influx_data.keys()) | set(layout_config.keys())
        all_lines = {l for l in all_lines if l and l.startswith('L')}

        linhas_list = []
        total_vazao = 0.0
        total_producao = 0.0
        total_oee = 0.0
        linhas_ativas_oee = 0

        for line_name in all_lines:
            d_metrics = django_metrics.get(line_name, {'vazao': 0.0, 'producao': 0.0})
            vazao = d_metrics['vazao']
            producao = d_metrics['producao']
            
            i_metrics = influx_data.get(line_name, {'oee': 0.0, 'status': 2})
            oee = i_metrics['oee']
            status_code = i_metrics['status']
            
            if status_code == 1 or vazao > 0:
                status_str = 'Produzindo'
            else:
                status_str = 'Parada'

            total_vazao += vazao
            total_producao += producao
            if oee > 0:
                total_oee += oee
                linhas_ativas_oee += 1

            linhas_list.append({
                'linha': line_name,
                'tph_real': round(vazao, 1),
                'status': status_str,
                'oee_real': round(oee, 1),
                'producao_real_t': round(producao, 1),
                'producao_planejada_t': 0,
                'oee_planejado': 85
            })

        avg_oee = (total_oee / linhas_ativas_oee) if linhas_ativas_oee > 0 else 0.0

        return {
            'vazao_total_tph': round(total_vazao, 1),
            'producao_real_t': round(total_producao, 1),
            'oee_fabril_real': round(avg_oee, 1),
            'oee_fabril_planejado': 85,
            'producao_planejada_t': round(factory_totals['producao_planejada_t'], 1),
            'vazao_necessaria_tph': round(factory_totals['vazao_necessaria_tph'], 1),
            'oee_global': round(avg_oee, 1),
            'disponibilidade_global': 0,
            'performance_global': 0,
            'qualidade_global': 0,
            'linhas': linhas_list,
            'layout_fabrica': [
                {
                    "linha": k,
                    "area": v["area"],
                    "posicao_x": v["pos_x"],
                    "posicao_y": v["pos_y"],
                    "w": v.get("w", 1),
                    "h": v.get("h", 1),
                    "critico": v["critico"]
                }
                for k, v in layout_config.items()
            ]
        }

    except Exception as e:
        logger.error(f"Erro geral em get_factory_kpis: {e}")
        return _get_empty_kpis()

def _get_empty_kpis():
    return {
        'vazao_total_tph': 0.0,
        'producao_real_t': 0.0,
        'oee_fabril_real': 0.0,
        'oee_fabril_planejado': 85,
        'producao_planejada_t': 0,
        'vazao_necessaria_tph': 0,
        'oee_global': 0.0,
        'disponibilidade_global': 0.0,
        'performance_global': 0.0,
        'qualidade_global': 0.0,
        'linhas': [],
        'layout_fabrica': []
    }

def get_factory_map_data():
    """
    Retorna dados para o mapa da fábrica.
    Hybrid: Layout hardcoded + Status/OEE from InfluxDB + Flow from Django
    """
    try:
        # 1. InfluxDB
        client = get_influx_client()
        query = """
            SELECT last("estado_maquina") as status, last("oee_realtime") as oee
            FROM "production"
            WHERE time > now() - 10m
            GROUP BY "line", "equipment"
        """
        influx_data = {}
        try:
            rs = client.query(query)
            line_stats = {}
            
            for (name, tags), points in rs.items():
                line_name = tags.get('line')
                if not line_name: continue
                
                points_list = list(points)
                if points_list:
                    p = points_list[0]
                    oee = float(p.get('oee', 0) or 0)
                    status = int(p.get('status', 2))
                    
                    if line_name not in line_stats:
                        line_stats[line_name] = {'oees': [], 'statuses': []}
                    
                    line_stats[line_name]['oees'].append(oee)
                    line_stats[line_name]['statuses'].append(status)
            
            # Calculate OLE
            for line_name, stats in line_stats.items():
                oees = stats['oees']
                statuses = stats['statuses']
                avg_oee = sum(oees) / len(oees) if oees else 0.0
                composite_status = 1 if 1 in statuses else 2
                
                influx_data[line_name] = {
                    'oee': avg_oee,
                    'status': composite_status
                }
        except:
            pass

        # 2. Django
        django_flow = {}
        name_map = {
            'Linha 01': 'L01', 'Linha 02': 'L02', 'Linha 03': 'L03', 'Linha 04': 'L04',
            'Linha 05': 'L05', 'Linha 06': 'L06', 'Linha 07': 'L07', 'Linha 08': 'L08',
            'Linha 09': 'L09', 'Linha 10': 'L10', 'Linha 11': 'L11', 'Linha 12': 'L12',
            'Linha 13': 'L13', 'Linha 14': 'L14', 'Linha 15': 'L15', 'Linha 16': 'L16',
            'Linha 17': 'L17', 'Linha 18': 'L18', 'Linha 19': 'L19', 'Linha 20': 'L20',
            'Linha 20_B': 'L20_B'
        }
        try:
            resp = requests.get(f"{DJANGO_API_URL}/metricas_fabrica_consolidadas/", timeout=3)
            if resp.status_code == 200:
                for l in resp.json():
                    raw = l.get('linha_nome') or l.get('linha_codigo')
                    canonical = name_map.get(raw, raw)
                    django_flow[canonical] = float(l.get('vazao_real_ton_hora') or 0)
        except:
            pass

        # Layout Config
        layout_config = {
            "L20": {"area": "PREPARO", "pos_x": 0, "pos_y": 0, "w": 2, "h": 1, "critico": False},
            "L15": {"area": "PREPARO", "pos_x": 0, "pos_y": 1.2, "w": 2, "h": 1, "critico": False},
            "L19": {"area": "PREPARO", "pos_x": 0, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
            "L20_B": {"area": "PREPARO", "pos_x": 1.6, "pos_y": 2.4, "w": 1.5, "h": 1.5, "critico": False},
            "L16": {"area": "MISTURA", "pos_x": 3.5, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
            "L06": {"area": "ENVASE PÓS", "pos_x": 4.8, "pos_y": 2.4, "w": 1, "h": 1.5, "critico": False},
            "L18": {"area": "MISTURA", "pos_x": 6, "pos_y": 1.5, "w": 2, "h": 0.8, "critico": False},
            "L17": {"area": "MISTURA", "pos_x": 6, "pos_y": 2.5, "w": 2, "h": 1.2, "critico": False},
            "L10": {"area": "EMBALAGEM", "pos_x": 8.5, "pos_y": 0, "w": 1, "h": 4, "critico": True},
            "L02": {"area": "MISTURA", "pos_x": 9.8, "pos_y": 0, "w": 1, "h": 4, "critico": True},
            "L01": {"area": "ENVASE LÍQ", "pos_x": 11.1, "pos_y": 0, "w": 1, "h": 4, "critico": False},
            "L09": {"area": "ENVASE", "pos_x": 12.4, "pos_y": 0, "w": 1, "h": 4, "critico": False}
        }

        # Merge
        all_lines = set(influx_data.keys()) | set(django_flow.keys()) | set(layout_config.keys())
        all_lines = {l for l in all_lines if l and l.startswith('L')}

        map_data = []
        for line in all_lines:
            i_data = influx_data.get(line, {'status': 2, 'oee': 0.0})
            flow = django_flow.get(line, 0.0)
            
            status_code = 1 if (i_data['status'] == 1 or flow > 0) else 2
            status_str = 'Produzindo' if status_code == 1 else 'Parada'

            layout = layout_config.get(line, {'pos_x': 0, 'pos_y': 0, 'w': 1, 'h': 1, 'area': 'N/A', 'critico': False})

            map_data.append({
                'linha': line,
                'status': status_str,
                'ole': round(i_data['oee'], 1),
                'tph': round(flow, 1),
                'layout': layout
            })
            
        return map_data

    except Exception as e:
        logger.error(f"Erro map data: {e}")
        return []
