from flask import Blueprint, request, jsonify
import logging
from services.diagnostics import get_equipment_sensors, client
from services.command_queue import add_command, get_pending_commands, peek_queue
import uuid

golden_state_bp = Blueprint('golden_state', __name__)
logger = logging.getLogger('GoldenStateBP')

@golden_state_bp.route('/apply', methods=['POST'])
def apply_golden_state():
    """
    APPLIES a saved Golden State Profile to the machine.
    Payload: { 'equipamento_codigo': 'E001', 'profile_timestamp': '...' }
    OR Payload: { 'equipamento_codigo': 'E001', 'profile_data': {...} }
    """
    try:
        data = request.json
        eq_codigo = data.get('equipamento_codigo')
        profile_time = data.get('profile_timestamp')
        
        if not eq_codigo:
            return jsonify({'error': 'equipamento_codigo required'}), 400

        # 1. Fetch Profile if timestamp provided, or use provided data
        profile = {}
        if profile_time:
            # Query Influx
            # careful with timestamp format in query
            # Assuming getting latest for now if not specific
            # But let's support exact lookup later.
            # Simplify: Frontend sends the full fields map?
            # Or fetches locally then sends.
            # Let's assume frontend sends the fields to apply for now to simplify logic?
            # No, backend should be source of truth.
            
            # Query specific profile
            # InfluxQL time comparison is string based
            query = f"SELECT * FROM golden_state_profile WHERE \"equipamento\" = '{eq_codigo}' AND time = '{profile_time}'"
            rs = client.query(query)
            points = list(rs.get_points())
            if not points:
                return jsonify({'error': 'Profile not found'}), 404
            profile = points[0]
        else:
            profile = data.get('profile_data')

        if not profile:
             return jsonify({'error': 'No profile data'}), 400

        # 2. Fetch Sensor Config from Django (to know what is a parameter and NodeIDs)
        sensors = get_equipment_sensors(eq_codigo)
        
        # 3. Filter and Build Commands
        commands = []
        for sensor in sensors:
            # Check if type is SETPOINT or LIMIT (Standard Django Types)
            s_type = sensor.get('tipo', '')
            if s_type not in ['SETPOINT', 'LIMIT']:
                continue
            
            tag_name = sensor.get('tag_influxdb')
            if not tag_name: continue
            
            # Get value from profile
            # Profile keys might be 'last_velocidade' or just 'velocidade' depending on how retrieved
            # get_points() usually removes 'last_' if grouped? No.
            # Saved profile has fields 'velocidade_atual', etc.
            
            val = profile.get(tag_name)
            if val is None:
                 # Try 'last_' prefix
                 val = profile.get(f'last_{tag_name}')
            
            if val is not None:
                # Find Node ID from Sensor (actually TagColeta)
                # Sensor model defines specific logic usually linked to a TagColeta via 'tag_influxdb' name match?
                # Or Sensor has NodeID?
                # Accessing 'models.py': Sensor has 'tag_influxdb'. TagColeta has 'node_id'.
                # We need to map Sensor -> TagColeta -> NodeID.
                # 'get_equipment_sensors' returns Sensor objects (dict).
                # We might need to fetch TagColeta too? 
                
                # Wait, 'get_equipment_sensors' calls Django URL /sensores/
                # Does /sensores/ return node_id? Not by default.
                # TagColeta is separate.
                pass 
                
        # CRITICAL: We need NodeID to write.
        # Solution: Backend Flask needs to ask Django to resolve TagConf?
        # Or Coletor resolves it?
        # Sender (Flask) sends {'tag_name': 'velocidade', 'value': 50}.
        # Coletor (Receiver) knows the configuration (NodeID map).
        # Coletor has 'self.configuracao'.
        # Perfect! Flask sends logical tag names. Coletor maps to NodeID.
        
                commands.append({
                    'tag': tag_name,
                    'value': val
                    # Coletor will handle types and node_id lookup
                })

        if not commands:
            return jsonify({'status': 'skipped', 'message': 'No writable parameters found in profile.'})

        # 4. Enqueue
        # We need LINE ID. Eq Code -> Line ID?
        # We can pass Line ID in payload or look it up.
        # Let's assume Coletor polls for ALL lines or we group by Line.
        # Coletor config has 'equipamentos'. It iterates them.
        # Let's just queue by 'ALL' or 'equipamento_codigo'
        # CommandQueue supports 'line_id', but we can abuse it or just use 'GLOBAL' if single coletor.
        # Or use eq_codigo as key?
        # Coletor iterates its equipments.
        # Better: Queue by Line ID.
        # We don't have Line ID easily here without lookup.
        # Let's queue by 'GLOBAL' and Coletor checks everything?
        # Or Just use 'default'.
        
        batch_id = str(uuid.uuid4())
        batch = {
            'id': batch_id,
            'equipamento_codigo': eq_codigo,
            'commands': commands
        }
        
        # Use 'global' queue for simplicity. Coletor is usually one instance per site or line.
        # If multiple collectors, they filter by what they own.
        add_command('GLOBAL', batch)
        
        logger.info(f"Queued {len(commands)} commands for {eq_codigo} (Batch {batch_id})")
        return jsonify({'status': 'queued', 'batch_id': batch_id, 'count': len(commands)})

    except Exception as e:
        logger.error(f"Error applying golden state: {e}")
        return jsonify({'error': str(e)}), 500

@golden_state_bp.route('/pending', methods=['GET'])
def get_commands():
    """
    Called by Coletor to get pending commands.
    Returns: List of batches.
    """
    cmds = get_pending_commands('GLOBAL')
    return jsonify(cmds)

@golden_state_bp.route('/callback', methods=['POST'])
def command_callback():
    """
    Receives status updates from Coletor.
    """
    data = request.json
    batch_id = data.get('batch_id')
    status = data.get('status')
    message = data.get('message')
    progress = data.get('progress')
    
    if batch_id and status:
        from services.command_queue import update_command_status
        update_command_status(batch_id, status, message, progress)
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Invalid data'}), 400

@golden_state_bp.route('/status/<batch_id>', methods=['GET'])
def get_status(batch_id):
    """
    Frontend polls this to see result.
    """
    from services.command_queue import get_command_status
    status = get_command_status(batch_id)
    return jsonify(status)
