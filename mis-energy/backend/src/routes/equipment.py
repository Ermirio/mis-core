# backend/src/routes/equipment.py
from flask import Blueprint, request, jsonify
import logging
from src.models.user import db
from src.models.equipment import Equipment
from src.models.gateway import Gateway

logger = logging.getLogger(__name__)
equipment_bp = Blueprint('equipment', __name__)

@equipment_bp.route('/equipments', methods=['GET'])
def get_equipments():
    """Lista todos os equipamentos, opcionalmente filtrado por hierarchy_id"""
    try:
        hierarchy_id = request.args.get('hierarchy_id')
        
        if hierarchy_id:
            equipments = Equipment.query.filter_by(hierarchy_id=int(hierarchy_id)).all()
        else:
            equipments = Equipment.query.all()
            
        return jsonify({
            'success': True,
            'data': [equipment.to_dict() for equipment in equipments]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@equipment_bp.route('/equipments/<int:equipment_id>', methods=['GET'])
def get_equipment(equipment_id):
    """Obtém um equipamento específico"""
    try:
        equipment = Equipment.query.get_or_404(equipment_id)
        return jsonify({
            'success': True,
            'data': equipment.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@equipment_bp.route('/equipments', methods=['POST'])
def create_equipment():
    """Cria um novo equipamento"""
    try:
        data = request.get_json()
        
        # Validações básicas
        if not data.get('name'):
            return jsonify({
                'success': False,
                'error': 'Nome é obrigatório'
            }), 400
        
        # Sanitizar campos que devem ser numéricos ou null
        for field in ['gateway_id', 'modbus_address', 'modbus_register', 'hierarchy_id', 
                      'standard_consumption', 'scale_factor', 'polling_interval']:
            if field in data and data[field] in ['', None, 'null', 'undefined']:
                data[field] = None
            elif field in data and data[field] is not None:
                # Tentar converter para int/float
                try:
                    if field in ['gateway_id', 'modbus_address', 'modbus_register', 'hierarchy_id', 'polling_interval']:
                        data[field] = int(data[field]) if data[field] else None
                    else:
                        data[field] = float(data[field]) if data[field] else None
                except (ValueError, TypeError):
                    data[field] = None
        
        # Boolean fields
        if 'is_entry_point' in data:
            if isinstance(data['is_entry_point'], str):
                 data['is_entry_point'] = data['is_entry_point'].lower() == 'true'
            else:
                 data['is_entry_point'] = bool(data['is_entry_point'])
            
        # Validações de endereçamento (apenas se gateway for fornecido)
        gateway_id = data.get('gateway_id')
        
        if gateway_id:
            # Verificar se o gateway existe
            gateway = Gateway.query.get(gateway_id)
            if not gateway:
                return jsonify({'success': False, 'error': 'Gateway não encontrado'}), 400
            
            # Determinar tipo de endereçamento baseado no protocolo do gateway
            protocol_type = gateway.protocol_type or 'modbus'
            
            if protocol_type == 'modbus':
                data['address_type'] = 'modbus'
                if not data.get('modbus_address'):
                    return jsonify({'success': False, 'error': 'Endereço Modbus é obrigatório quando gateway Modbus selecionado'}), 400
                if not data.get('modbus_register'):
                    return jsonify({'success': False, 'error': 'Registro é obrigatório quando gateway Modbus selecionado'}), 400
                    
                # Verificar duplicidade Modbus
                existing = Equipment.query.filter_by(
                    gateway_id=gateway_id,
                    modbus_address=data.get('modbus_address')
                ).first()
                if existing:
                    return jsonify({'success': False, 'error': 'Já existe um equipamento com este endereço Modbus neste gateway'}), 400
            elif protocol_type == 'opc':
                data['address_type'] = 'opc'
                if not data.get('opc_node_id'):
                    return jsonify({'success': False, 'error': 'NodeID é obrigatório quando gateway OPC UA selecionado'}), 400
        else:
            # Sem gateway - equipamento ainda não configurado para comunicação
            data['address_type'] = None
        
        # Validação de medidor de entrada único por hierarquia
        if data.get('is_entry_point') is True and data.get('hierarchy_id'):
            from src.models.hierarchy_model import Hierarchy
            hierarchy = Hierarchy.query.get(data.get('hierarchy_id'))
            if hierarchy:
                existing = Equipment.query.filter(
                    Equipment.hierarchy_id == data.get('hierarchy_id'),
                    Equipment.is_entry_point == True
                ).first()
                if existing:
                    return jsonify({
                        'success': False,
                        'error': f'Já existe um medidor de entrada para a {hierarchy.type} {hierarchy.name}: "{existing.name}". Só é permitido um medidor de entrada por nível.'
                    }), 400
        
        # Auto-tagging Logic
        if not data.get('tag') and data.get('hierarchy_id'):
            from src.models.hierarchy_model import Hierarchy
            hierarchy = Hierarchy.query.get(data.get('hierarchy_id'))
            if hierarchy:
                # Build path codes: Root -> Child -> ...
                codes = []
                current = hierarchy
                while current:
                    if current.code:
                        codes.insert(0, current.code)
                    current = current.parent
                
                # Add Equipment Type Prefix
                type_map = {
                    'motor': 'MTR',
                    'resistor': 'RES',
                    'lighting': 'LGT',
                    'compressor': 'CMP',
                    'generic': 'EQP',
                    'energy_meter': 'ENM',
                    'production_meter': 'PRD',
                    'counter': 'CNT',
                    'scale': 'SCL',
                    'flow_meter': 'FLW'
                }
                type_code = type_map.get(data.get('equipment_type', 'generic'), 'EQP')
                codes.append(type_code)
                
                # Generate Sequence
                # Find last equipment with same prefix to increment
                prefix = "-".join(codes)
                last_eq = Equipment.query.filter(Equipment.tag.like(f"{prefix}-%")).order_by(Equipment.id.desc()).first()
                
                seq = 1
                if last_eq and last_eq.tag:
                    try:
                        parts = last_eq.tag.split('-')
                        if parts:
                            seq = int(parts[-1]) + 1
                    except:
                        pass
                
                data['tag'] = f"{prefix}-{seq:03d}"

        equipment = Equipment.from_dict(data)
        db.session.add(equipment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': equipment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@equipment_bp.route('/equipments/<int:equipment_id>', methods=['PUT'])
def update_equipment(equipment_id):
    """Atualiza um equipamento"""
    try:
        equipment = Equipment.query.get_or_404(equipment_id)
        data = request.get_json()
        
        # Sanitizar campos que devem ser numéricos ou null (igual ao POST)
        for field in ['gateway_id', 'modbus_address', 'modbus_register', 'hierarchy_id', 
                      'standard_consumption', 'scale_factor', 'polling_interval']:
            if field in data and data[field] in ['', None, 'null', 'undefined']:
                data[field] = None
            elif field in data and data[field] is not None:
                try:
                    if field in ['gateway_id', 'modbus_address', 'modbus_register', 'hierarchy_id', 'polling_interval']:
                        data[field] = int(data[field]) if data[field] else None
                    else:
                        data[field] = float(data[field]) if data[field] else None
                except (ValueError, TypeError):
                    data[field] = None

        # Boolean fields
        if 'is_entry_point' in data:
            if isinstance(data['is_entry_point'], str):
                 data['is_entry_point'] = data['is_entry_point'].lower() == 'true'
            else:
                 data['is_entry_point'] = bool(data['is_entry_point'])
        
        # Validação de medidor de entrada único por hierarquia
        if data.get('is_entry_point') is True and (data.get('hierarchy_id') or equipment.hierarchy_id):
            target_hierarchy_id = data.get('hierarchy_id') or equipment.hierarchy_id
            
            from src.models.hierarchy_model import Hierarchy
            hierarchy = Hierarchy.query.get(target_hierarchy_id)
            if hierarchy:
                existing = Equipment.query.filter(
                    Equipment.hierarchy_id == target_hierarchy_id,
                    Equipment.is_entry_point == True,
                    Equipment.id != equipment_id  # Excluir o próprio equipamento
                ).first()
                if existing:
                    return jsonify({
                        'success': False,
                        'error': f'Já existe um medidor de entrada para a {hierarchy.type} {hierarchy.name}: "{existing.name}". Só é permitido um medidor de entrada por nível.'
                    }), 400
        
        # Atualizar campos
        if 'name' in data:
            equipment.name = data['name']
        if 'description' in data:
            equipment.description = data['description']
        if 'location' in data:
            equipment.location = data['location']
        if 'area' in data:
            equipment.area = data['area']
        if 'hierarchy_id' in data:
            equipment.hierarchy_id = data['hierarchy_id']
        if 'equipment_type' in data:
            equipment.equipment_type = data['equipment_type']
        if 'parameters' in data:
            equipment.parameters = data['parameters']
        if 'standard_consumption' in data:
            equipment.standard_consumption = data['standard_consumption']
        if 'address_type' in data:
            equipment.address_type = data['address_type']
        if 'gateway_id' in data:
            equipment.gateway_id = data['gateway_id']
        if 'modbus_address' in data:
            equipment.modbus_address = data['modbus_address']
        if 'opc_node_id' in data:
            equipment.opc_node_id = data['opc_node_id']
        if 'modbus_register' in data:
            equipment.modbus_register = data['modbus_register']
        if 'register_type' in data:
            equipment.register_type = data['register_type']
        if 'data_type' in data:
            equipment.data_type = data['data_type']
        if 'scale_factor' in data:
            equipment.scale_factor = data['scale_factor']
        if 'unit' in data:
            equipment.unit = data['unit']
        if 'is_active' in data:
            equipment.is_active = data['is_active']
        if 'polling_interval' in data:
            equipment.polling_interval = data['polling_interval']
        if 'meter_type' in data:
            equipment.meter_type = data['meter_type']
        if 'is_entry_point' in data:
            equipment.is_entry_point = data['is_entry_point']
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': equipment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@equipment_bp.route('/equipments/<int:equipment_id>', methods=['DELETE'])
def delete_equipment(equipment_id):
    """Remove um equipamento"""
    try:
        equipment = Equipment.query.get_or_404(equipment_id)
        
        db.session.delete(equipment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Equipamento removido com sucesso'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@equipment_bp.route('/equipments/by-gateway/<int:gateway_id>', methods=['GET'])
def get_equipments_by_gateway(gateway_id):
    """Lista equipamentos de um gateway específico"""
    try:
        equipments = Equipment.query.filter_by(gateway_id=gateway_id).all()
        return jsonify({
            'success': True,
            'data': [equipment.to_dict() for equipment in equipments]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@equipment_bp.route('/equipments/<int:equipment_id>/read', methods=['POST'])
def read_equipment_value(equipment_id):
    """Lê valor atual do equipamento via Modbus"""
    try:
        from src.services.modbus_client import modbus_service
        from src.services.influxdb_client import influxdb_service
        from src.services.simulation_service import simulation_service
        from datetime import datetime
        
        # Verificar se modo simulação está ativo
        if simulation_service.is_simulation_active():
            simulated_result = simulation_service.simulate_modbus_read(equipment_id)
            if simulated_result:
                return jsonify(simulated_result)
        
        # Código original para leitura real
        equipment = Equipment.query.get_or_404(equipment_id)
        # Ler valor
        gateway = equipment.gateway
        
        if not gateway:
            return jsonify({
                'success': False,
                'error': 'Gateway não encontrado para este equipamento'
            }), 400
        
        if gateway.protocol_type == 'opc':
            # Leitura OPC UA real
            from src.services.opc_client import opc_client_service
            
            if not equipment.opc_node_id:
                return jsonify({
                    'success': False,
                    'error': 'NodeID OPC não configurado para este equipamento'
                }), 400
            
            result = opc_client_service.read_value(
                opc_url=gateway.opc_url,
                node_id=equipment.opc_node_id,
                timeout=gateway.timeout or 5
            )
            
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 500
        else:
            # Leitura Modbus
            gateway = equipment.gateway
            
            if not gateway:
                return jsonify({
                    'success': False,
                    'error': 'Gateway não encontrado para este equipamento'
                }), 400
            
            result = modbus_service.read_register(
                ip_address=gateway.ip_address,
                port=gateway.port,
                modbus_address=equipment.modbus_address,
                register=equipment.opc_register,
                register_type=equipment.register_type,
                data_type=equipment.data_type
            )
            
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 500
        
        # Aplicar fator de escala
        scaled_value = result['converted_value'] * equipment.scale_factor
        
        # Atualizar último valor no equipamento
        equipment.last_value = scaled_value
        equipment.last_reading_at = datetime.now()
        db.session.commit()
        
        # Armazenar no InfluxDB se configurado
        try:
            influxdb_service.write_measurement(
                equipment_id=equipment.id,
                equipment_name=equipment.name,
                value=scaled_value,
                unit=equipment.unit,
                location=equipment.location,
                area=equipment.area,
                hierarchy_path=equipment._get_hierarchy_path(),
                equipment_type=equipment.equipment_type
            )
        except Exception as e:
            # Log do erro mas não falha a operação
            logger.warning(f"Erro ao salvar no InfluxDB: {e}")
        
        return jsonify({
            'success': True,
            'data': {
                'equipment_id': equipment_id,
                'value': scaled_value,
                'unit': equipment.unit,
                'timestamp': result['timestamp'],
                'raw_value': result['raw_value'],
                'converted_value': result['converted_value'],
                'scale_factor': equipment.scale_factor
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

