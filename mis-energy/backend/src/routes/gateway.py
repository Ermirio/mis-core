# backend/src/routes/gateway.py
from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.gateway import Gateway
from src.models.equipment import Equipment

gateway_bp = Blueprint('gateway', __name__)

@gateway_bp.route('/gateways', methods=['GET'])
def get_gateways():
    """Lista todos os gateways"""
    try:
        gateways = Gateway.query.all()
        return jsonify({
            'success': True,
            'data': [gateway.to_dict() for gateway in gateways]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gateway_bp.route('/gateways/<int:gateway_id>', methods=['GET'])
def get_gateway(gateway_id):
    """Obtém um gateway específico"""
    try:
        gateway = Gateway.query.get_or_404(gateway_id)
        return jsonify({
            'success': True,
            'data': gateway.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gateway_bp.route('/gateways', methods=['POST'])
def create_gateway():
    print(">>> PEDIDO PARA CRIAR GATEWAY CHEGOU! <<<")  # <--- ADICIONE ESTA LINHA
    """Cria um novo gateway"""
    try:
        data = request.get_json()
        
        # Validações básicas
        if not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Nome é obrigatório'
            }), 400
        
        if not data.get('ip_address'):
            return jsonify({
                'success': False,
                'error': 'Endereço IP é obrigatório'
            }), 400
        
        # Verificar se já existe gateway com mesmo IP e porta
        existing = Gateway.query.filter_by(
            ip_address=data.get('ip_address'),
            port=data.get('port', 502)
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': 'Já existe um gateway com este IP e porta'
            }), 400
        
        gateway = Gateway.from_dict(data)
        db.session.add(gateway)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': gateway.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gateway_bp.route('/gateways/<int:gateway_id>', methods=['PUT'])
def update_gateway(gateway_id):
    """Atualiza um gateway"""
    try:
        gateway = Gateway.query.get_or_404(gateway_id)
        data = request.get_json()
        
        # Atualizar campos
        if 'name' in data:
            gateway.name = data['name']
        if 'description' in data:
            gateway.description = data['description']
        if 'ip_address' in data:
            gateway.ip_address = data['ip_address']
        if 'port' in data:
            gateway.port = data['port']
        if 'timeout' in data:
            gateway.timeout = data['timeout']
        if 'is_active' in data:
            gateway.is_active = data['is_active']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': gateway.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gateway_bp.route('/gateways/<int:gateway_id>', methods=['DELETE'])
def delete_gateway(gateway_id):
    """Remove um gateway"""
    try:
        gateway = Gateway.query.get_or_404(gateway_id)
        
        # Verificar se há equipamentos associados
        equipment_count = Equipment.query.filter_by(gateway_id=gateway_id).count()
        if equipment_count > 0:
            return jsonify({
                'success': False,
                'error': f'Não é possível remover o gateway. Existem {equipment_count} equipamentos associados.'
            }), 400
        
        db.session.delete(gateway)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Gateway removido com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@gateway_bp.route('/gateways/<int:gateway_id>/test', methods=['POST'])
def test_gateway_connection(gateway_id):
    """Testa conexão com o gateway"""
    try:
        from src.services.modbus_client import modbus_service
        from src.services.simulation_service import simulation_service
        
        # Verificar se modo simulação está ativo
        if simulation_service.is_simulation_active():
            simulated_result = simulation_service.simulate_gateway_test(gateway_id)
            if simulated_result:
                return jsonify(simulated_result)
        
        # Código original para teste real
        gateway = Gateway.query.get_or_404(gateway_id)
        
        # Testar conexão real com Modbus
        result = modbus_service.test_connection(
            gateway.ip_address, 
            gateway.port, 
            gateway.timeout
        )
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

