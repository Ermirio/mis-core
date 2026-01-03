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
    """Lista todos os equipamentos, opcionalmente filtrado por hierarchy_id
    
    Query params:
        hierarchy_id: ID da hierarquia para filtrar
        recursive: Se 'true', inclui equipamentos de todas as sub-hierarquias
    """
    try:
        from src.models.hierarchy_model import Hierarchy
        
        hierarchy_id = request.args.get('hierarchy_id')
        recursive = request.args.get('recursive', 'false').lower() == 'true'
        
        if hierarchy_id:
            hierarchy_id = int(hierarchy_id)
            
            if recursive:
                # Buscar todos os IDs de hierarquia recursivamente
                def get_all_child_ids(parent_id):
                    """Retorna lista de IDs incluindo parent e todos os filhos recursivamente"""
                    ids = [parent_id]
                    children = Hierarchy.query.filter_by(parent_id=parent_id).all()
                    for child in children:
                        ids.extend(get_all_child_ids(child.id))
                    return ids
                
                all_hierarchy_ids = get_all_child_ids(hierarchy_id)
                equipments = Equipment.query.filter(Equipment.hierarchy_id.in_(all_hierarchy_ids)).all()
            else:
                equipments = Equipment.query.filter_by(hierarchy_id=hierarchy_id).all()
        else:
            equipments = Equipment.query.all()
            
        return jsonify({
            'success': True,
            'data': [equipment.to_dict() for equipment in equipments]
        })
    except Exception as e:
        logger.error(f"Erro ao buscar equipamentos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@equipment_bp.route('/equipments/collector-config', methods=['GET'])
def get_collector_config():
    """Configuração para o Coletor Dedicado (OPC)"""
    try:
        equipments = Equipment.query.filter_by(address_type='opc', is_active=True).all()
        config = []
        for eq in equipments:
            if eq.gateway:
                config.append({
                    'id': eq.id,
                    'tag': eq.tag or eq.name,
                    'type': 'opc',
                    'gateway': {
                        'ip_address': eq.gateway.ip_address,
                        'port': eq.gateway.port,
                        'opc_url': eq.gateway.opc_url  # URL completa OPC
                    },
                    'nodes': {
                        'voltage_a': eq.opc_node_voltage_a,
                        'voltage_b': eq.opc_node_voltage_b,
                        'voltage_c': eq.opc_node_voltage_c,
                        'current_a': eq.opc_node_current_a,
                        'current_b': eq.opc_node_current_b,
                        'current_c': eq.opc_node_current_c,
                        'power_kw': eq.opc_node_power_kw,
                        'energy_kwh': eq.opc_node_energy_kwh,
                        'demand_kw': eq.opc_node_demand_kw,
                        'power_factor': eq.opc_node_power_factor,
                        # Production Nodes (loaded from parameters)
                        'production_total': eq.parameters.get('production_total_node'),
                        'production_rate': eq.parameters.get('production_rate_node'),
                        'production_sku': eq.parameters.get('production_sku_node'),
                        'production_format': eq.parameters.get('production_format_node')
                    }
                })
        return jsonify({
            'success': True,
            'data': config
        })
    except Exception as e:
        logger.error(f"Erro config coletor: {e}")
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
                      'standard_consumption', 'scale_factor', 'polling_interval',
                      'tariff_kwh', 'tariff_demand']:
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
        # Multi-metric OPC addresses
        if 'opc_node_power_kw' in data:
            equipment.opc_node_power_kw = data['opc_node_power_kw'] or None
        if 'opc_node_energy_kwh' in data:
            equipment.opc_node_energy_kwh = data['opc_node_energy_kwh'] or None
        if 'opc_node_demand_kw' in data:
            equipment.opc_node_demand_kw = data['opc_node_demand_kw'] or None
        if 'opc_node_power_factor' in data:
            equipment.opc_node_power_factor = data['opc_node_power_factor'] or None
        # Power quality fields
        if 'opc_node_voltage_a' in data:
            equipment.opc_node_voltage_a = data['opc_node_voltage_a'] or None
        if 'opc_node_voltage_b' in data:
            equipment.opc_node_voltage_b = data['opc_node_voltage_b'] or None
        if 'opc_node_voltage_c' in data:
            equipment.opc_node_voltage_c = data['opc_node_voltage_c'] or None
        if 'opc_node_current_a' in data:
            equipment.opc_node_current_a = data['opc_node_current_a'] or None
        if 'opc_node_current_b' in data:
            equipment.opc_node_current_b = data['opc_node_current_b'] or None
        if 'opc_node_current_c' in data:
            equipment.opc_node_current_c = data['opc_node_current_c'] or None
        # Cost configuration
        if 'tariff_kwh' in data:
            equipment.tariff_kwh = float(data['tariff_kwh']) if data['tariff_kwh'] else None
        if 'tariff_demand' in data:
            equipment.tariff_demand = float(data['tariff_demand']) if data['tariff_demand'] else None
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
        
        # Verificar se modo simulação está ativo via HEADER (Cliente específico)
        is_mock_mode = request.headers.get('X-Mock-Mode') == 'true'
        
        if is_mock_mode:
            # Se mock mode ativo, força simulação
            simulated_result = simulation_service.simulate_modbus_read(equipment_id)
            if simulated_result:
                return jsonify(simulated_result)
        
        # Código para leitura real (se mock mode não estiver ativo)
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
            
            # Determine which node to read based on equipment type
            node_to_read = None
            
            if equipment.meter_type == 'production':
                # For production meters, prioritize production-specific nodes
                node_to_read = equipment.parameters.get('production_rate_node') or equipment.parameters.get('production_total_node')
            
            if not node_to_read:
                # Fallback: For energy meters or if no production node, use power node or legacy
                node_to_read = equipment.opc_node_power_kw or equipment.opc_node_id
            
            if not node_to_read:
                return jsonify({
                    'success': False,
                    'error': 'Nenhum NodeID OPC configurado para este equipamento. Configure os endereços na aba Endereçamento.'
                }), 400
            
            result = opc_client_service.read_value(
                opc_url=gateway.opc_url,
                node_id=node_to_read,
                timeout=gateway.timeout or 5
            )
            
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': f"Erro OPC UA: \"{result['error']}\""
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
                register=equipment.modbus_register,
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
            # Determinar código da tag e métrica para compatibilidade com histórico
            tag_code = equipment.tag or equipment.name
            metric_name = 'power_kw' if equipment.meter_type == 'energy' else 'generic'
            
            influxdb_service.write_measurement(
                equipment_id=equipment.id,
                equipment_name=equipment.name,
                value=scaled_value,
                unit=equipment.unit,
                location=equipment.location,
                area=equipment.area,
                hierarchy_path=equipment._get_hierarchy_path(),
                equipment_type=equipment.equipment_type,
                tag_code=tag_code,
                metric_name=metric_name
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


# ===== NEW MULTI-METRIC ENDPOINTS =====

@equipment_bp.route('/equipments/<int:equipment_id>/metrics', methods=['GET'])
def get_equipment_metrics(equipment_id):
    """
    Retorna as 4 métricas principais em tempo real:
    - Potência ativa (kW)
    - Energia acumulada (kWh)
    - Demanda máxima (kW)
    - Fator de potência
    """
    try:
        from src.services.opc_client import opc_client_service

        from datetime import datetime
        

        # SE NÃO ESTÁ EM MOCK MODE, TENTA LEITURA REAL

        # SE NÃO ESTÁ EM MOCK MODE, TENTA LEITURA REAL
        equipment = Equipment.query.get_or_404(equipment_id)
        gateway = equipment.gateway
        
        metrics = {
            'power_kw': None,
            'energy_kwh': None,
            'demand_kw': None,
            'power_factor': None
        }
        
        if equipment.meter_type == 'production':
            metrics.update({
                'production_total': None,
                'production_rate': None,
                'efficiency_kwh_ton': None
            })
        
        # Ler cada métrica via OPC/Modbus REAL
        if gateway and gateway.protocol_type == 'opc':
            opc_config = {
                'url': gateway.opc_url,
                'timeout': gateway.timeout or 5
            }
            
            # Helper para leitura segura
            def safe_read(node_id, scale=1.0):
                if not node_id: return None
                try:
                    res = opc_client_service.read_value(opc_config['url'], node_id, opc_config['timeout'])
                    return res.get('converted_value') * scale if res.get('success') and res.get('converted_value') is not None else None
                except:
                    return None

            metrics['power_kw'] = safe_read(equipment.opc_node_power_kw, equipment.scale_factor)
            metrics['energy_kwh'] = safe_read(equipment.opc_node_energy_kwh, equipment.scale_factor)
            metrics['demand_kw'] = safe_read(equipment.opc_node_demand_kw, equipment.scale_factor)
            metrics['power_factor'] = safe_read(equipment.opc_node_power_factor)

            # --- PRODUCTION MODE Logic ---
            if equipment.meter_type == 'production':
                # Production specific nodes from parameters
                prod_total_node = equipment.parameters.get('production_total_node')
                prod_rate_node = equipment.parameters.get('production_rate_node')
                prod_format_node = equipment.parameters.get('production_format_node') # Not used for metric but maybe needed?
                
                metrics['production_total'] = safe_read(prod_total_node, 1.0) # Assume scale 1.0 or need param?
                metrics['production_rate'] = safe_read(prod_rate_node, 1.0) 
                
                # For efficiency calculation, we need power_kw from an associated energy meter
                # Find the entry-point energy meter on the same hierarchy
                if metrics.get('power_kw') is None and equipment.hierarchy_id:
                    energy_meter = Equipment.query.filter(
                        Equipment.hierarchy_id == equipment.hierarchy_id,
                        Equipment.meter_type == 'energy',
                        Equipment.is_entry_point == True,
                        Equipment.id != equipment.id
                    ).first()
                    
                    if energy_meter and energy_meter.gateway and energy_meter.gateway.protocol_type == 'opc':
                        energy_opc_config = {
                            'url': energy_meter.gateway.opc_url,
                            'timeout': energy_meter.gateway.timeout or 5
                        }
                        def safe_read_energy(node_id, scale=1.0):
                            if not node_id: return None
                            try:
                                res = opc_client_service.read_value(energy_opc_config['url'], node_id, energy_opc_config['timeout'])
                                return res.get('converted_value') * scale if res.get('success') and res.get('converted_value') is not None else None
                            except:
                                return None
                        metrics['power_kw'] = safe_read_energy(energy_meter.opc_node_power_kw, energy_meter.scale_factor)
                
                # Real-time Efficiency (kWh / Ton) calculation
                # eff = Power (kW) / Rate (Ton/h) -> kWh/Ton
                pwr = metrics.get('power_kw')
                rate = metrics.get('production_rate')
                
                if pwr and rate and rate > 0:
                    metrics['efficiency_kwh_ton'] = round(pwr / rate, 2)
                else:
                    metrics['efficiency_kwh_ton'] = 0.0 if (pwr is not None and rate is not None) else None

        # Se leitura real falhou, retornamos None
        # ZERO SIMULATION


        # Se leitura real falhou e NÃO estamos em mock mode, retornamos o que temos (mesmo que seja None)
        # Garantia de NÃO usar dados fakes se o usuário pediu dados reais.
        
        # Calcular custos reais baseados nos dados lidos (se disponíveis)
        tariff = equipment.tariff_kwh or 0.5
        cost_per_hour = (metrics['power_kw'] or 0) * tariff
        
        # Specific cost for production (R$/Ton)
        cost_per_ton = None
        if metrics.get('efficiency_kwh_ton'):
             cost_per_ton = metrics['efficiency_kwh_ton'] * tariff

        return jsonify({
            'success': True,
            'data': {
                'metrics': metrics,
                'cost': {
                    'per_hour': cost_per_hour,
                    'per_day': cost_per_hour * 24, # Projeção simples
                    'per_ton': cost_per_ton,
                    'tariff_kwh': tariff
                },
                'timestamp': datetime.now().isoformat(),
                'alerts': {
                    'high_demand': (metrics['demand_kw'] or 0) > 100, # Lógica simples
                    'low_power_factor': (metrics.get('power_factor') or 0) < 0.92
                }
            }
        })

        
    except Exception as e:
        logger.error(f"Erro ao obter métricas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@equipment_bp.route('/equipments/<int:equipment_id>/history', methods=['GET'])
def get_equipment_history(equipment_id):
    """
    Retorna histórico de uma métrica específica
    
    Query params:
        metric: power_kw, energy_kwh, demand_kw, power_factor
        period: 1h, 6h, 12h, 24h, 7d, 30d
    """
    try:
        from datetime import datetime, timedelta
        import requests
        
        equipment = Equipment.query.get_or_404(equipment_id)
        
        metric = request.args.get('metric', 'power_kw')
        period = request.args.get('period', '24h')
        
        # Calcular time range
        period_map = {
            '1h': timedelta(hours=1),
            '6h': timedelta(hours=6),
            '12h': timedelta(hours=12),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30)
        }
        delta = period_map.get(period, timedelta(hours=24))
        start_time = datetime.now() - delta
        
        # Consultar InfluxDB
        # Use configuration from influxdb_service to ensure consistency
        influx_host = 'influxdb' 
        influx_port = 8086
        database = 'industrial_db' # Was db_energy, but logs show industrial_db
        username = 'admin'
        password = 'admin123'
        
        # tag corresponde ao equipamento_codigo (F001-A001-L001-ENM-001) ou nome como fallback
        eq_tag = equipment.tag or equipment.name
        
        # DEBUG: Log da query para verificação
        logger.info(f"Buscando histórico para TAG: {eq_tag}, Metric: {metric}, Period: {period}")
        
        query = f'''
            SELECT mean("value") as value 
            FROM "energy_consumption" 
            WHERE "tag" = '{eq_tag}'
            AND "metric" = '{metric}'
            AND time > '{start_time.isoformat()}Z'
            GROUP BY time(5m) fill(none)
        '''
        
        try:
            logging.info(f"InfluxDB Query: {query}")
            response = requests.get(
                f'http://{influx_host}:{influx_port}/query',
                params={'db': database, 'q': query, 'u': username, 'p': password},
                timeout=5
            )
            
            logging.info(f"InfluxDB Response Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                # logging.info(f"InfluxDB Data: {data}") # Pode ser verboso
                series = data.get('results', [{}])[0].get('series', [{}])
                
                if not series:
                   history = []
                else:
                   values = series[0].get('values', [])
                   history = [
                       {'timestamp': v[0], 'value': v[1]} 
                       for v in values if v[1] is not None
                   ]
            else:
                logging.error(f"InfluxDB Error Body: {response.text}")
                history = []
        except:
            # Fallback: ZERO SIMULATION
            history = []

        
        # Calcular estatísticas
        if history:
            values = [h['value'] for h in history if h['value']]
            stats = {
                'min': round(min(values), 2) if values else None,
                'max': round(max(values), 2) if values else None,
                'avg': round(sum(values) / len(values), 2) if values else None,
                'count': len(values)
            }
        else:
            stats = {'min': None, 'max': None, 'avg': None, 'count': 0}
        
        return jsonify({
            'success': True,
            'data': {
                'equipment_id': equipment_id,
                'equipment_name': equipment.name,
                'metric': metric,
                'period': period,
                'history': history[-100:],  # Limitar a 100 pontos
                'stats': stats
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter histórico: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@equipment_bp.route('/equipments/<int:equipment_id>/cost-analysis', methods=['GET'])
def get_equipment_cost_analysis(equipment_id):
    """
    Retorna análise de custo detalhada
    """
    try:
        from datetime import datetime, timedelta
        import requests
        import sys
        
        equipment = Equipment.query.get_or_404(equipment_id)
        
        # Initialization
        now = datetime.now()
        period = request.args.get('period', '7d')
        tariff = equipment.tariff_kwh or 0.5
        
        period_map = {
            '24h': (24, 'hour'),
            '7d': (7, 'day'),
            '30d': (30, 'day')
        }
        count, unit = period_map.get(period, (7, 'day'))
        
        timeline = []
        total_cost = 0
        total_energy = 0
        
        # Configuration
        influx_host = 'influxdb'
        influx_port = 8086
        database = 'industrial_db'
        username = 'admin'
        password = 'admin123'
        
        eq_tag = equipment.tag or equipment.name
        group_by = '1h' if period == '24h' else '1d'
        start_time = now - timedelta(hours=24 if period == '24h' else (7*24 if period == '7d' else 30*24))
        
        # MAIN QUERY: Aggregation
        query = f'''
            SELECT mean("value") as avg_power
            FROM "energy_consumption" 
            WHERE "tag" = '{eq_tag}'
            AND time > '{start_time.isoformat()}Z'
            GROUP BY time({group_by}) fill(0)
        '''
        
        print(f"DEBUG QUERY: {query}", file=sys.stderr)
        
        try:
            # Using Basic Auth
            response = requests.get(
                f'http://{influx_host}:{influx_port}/query',
                params={'db': database, 'q': query},
                auth=(username, password),
                timeout=5
            )
            
            print(f"DEBUG STATUS: {response.status_code}", file=sys.stderr)
            
            if response.status_code == 200:
                data = response.json()
                series = data.get('results', [{}])[0].get('series', [])
                
                if series:
                    values = series[0].get('values', [])
                    hours_per_bucket = 1 if group_by == '1h' else 24
                    
                    for v in values:
                        ts = v[0]
                        avg_power = v[1] if v[1] is not None else 0
                        kwh = avg_power * hours_per_bucket
                        cost = kwh * tariff
                        
                        timeline.append({
                            'timestamp': ts,
                            'energy_kwh': round(kwh, 2),
                            'cost_brl': round(cost, 2)
                        })
                        total_energy += kwh
                        total_cost += cost
                else:
                    print("DEBUG: Main query empty. Logic Fallback.", file=sys.stderr)
                    # FALLBACK: Raw Data
                    fallback_query = f'''
                        SELECT "value" 
                        FROM "energy_consumption" 
                        WHERE "tag" = '{eq_tag}'
                        AND time > '{start_time.isoformat()}Z'
                    '''
                    print(f"DEBUG FALLBACK: {fallback_query}", file=sys.stderr)
                    
                    fb_response = requests.get(
                        f'http://{influx_host}:{influx_port}/query',
                        params={'db': database, 'q': fallback_query},
                        auth=(username, password),
                        timeout=5
                    )
                    
                    if fb_response.status_code == 200:
                        fb_data = fb_response.json()
                        fb_series = fb_data.get('results', [{}])[0].get('series', [])
                        
                        if fb_series:
                            fb_values = fb_series[0].get('values', [])
                            # Crude average
                            total_val = sum(v[1] for v in fb_values if v[1] is not None)
                            count_val = len(fb_values)
                            avg_val = total_val / count_val if count_val > 0 else 0
                            
                            hours_total = 24 if period == '24h' else (7*24)
                            total_energy = avg_val * hours_total
                            total_cost = total_energy * tariff
                            
                            # Single point
                            timeline.append({
                                'timestamp': now.isoformat(),
                                'energy_kwh': round(total_energy, 2),
                                'cost_brl': round(total_cost, 2)
                            })
            else:
                print(f"DEBUG ERROR BODY: {response.text}", file=sys.stderr)
                
        except Exception as e:
            print(f"DEBUG EXCEPTION: {e}", file=sys.stderr)
            logger.error(f"Erro query custo: {e}")

        # Identificar picos (top 3 custos)
        sorted_timeline = sorted(timeline, key=lambda x: x['cost_brl'], reverse=True)
        peaks = sorted_timeline[:3]
        
        return jsonify({
            'success': True,
            'data': {
                'equipment_id': equipment_id,
                'equipment_name': equipment.name,
                'period': period,
                'tariff_kwh': tariff,
                'total': {
                    'energy_kwh': round(total_energy, 2),
                    'cost_brl': round(total_cost, 2),
                    'avg_per_day': round(total_cost / max(count, 1), 2)
                },
                'timeline': timeline,
                'peaks': peaks,
                'projection': {
                    'month': round(total_cost / count * 30, 2) if count else 0,
                    'year': round(total_cost / count * 365, 2) if count else 0
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter análise de custo: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@equipment_bp.route('/equipments/<int:equipment_id>/power-quality', methods=['GET'])
def get_equipment_power_quality(equipment_id):
    """
    Retorna métricas de qualidade de energia (V/A por fase)
    """
    try:
        from src.services.opc_client import opc_client_service
        from datetime import datetime
        import random
        
        equipment = Equipment.query.get_or_404(equipment_id)
        gateway = equipment.gateway
        
        power_quality = {
            'voltage': {'a': None, 'b': None, 'c': None},
            'current': {'a': None, 'b': None, 'c': None}
        }
        
        # Verificar se tem campos configurados
        has_pq_config = any([
            equipment.opc_node_voltage_a,
            equipment.opc_node_voltage_b,
            equipment.opc_node_voltage_c,
            equipment.opc_node_current_a,
            equipment.opc_node_current_b,
            equipment.opc_node_current_c
        ])
        
        if not has_pq_config:
            return jsonify({
                'success': True,
                'data': {
                    'equipment_id': equipment_id,
                    'available': False,
                    'message': 'Qualidade de energia não configurada para este equipamento'
                }
            })
        
        # Tentar leitura REAL do OPC
        if gateway and gateway.protocol_type == 'opc':
            # Usar opc_url se disponível, senão construir a partir de ip:port
            opc_url = gateway.opc_url or f"opc.tcp://{gateway.ip_address}:{gateway.port or 4840}"
            
            def safe_opc_read(node_id):
                if not node_id:
                    return None
                try:
                    result = opc_client_service.read_value(opc_url, node_id, gateway.timeout or 5)
                    return result.get('converted_value') if result.get('success') else None
                except Exception as e:
                    logger.warning(f"Erro OPC read {node_id}: {e}")
                    return None
            
            power_quality = {
                'voltage': {
                    'a': safe_opc_read(equipment.opc_node_voltage_a),
                    'b': safe_opc_read(equipment.opc_node_voltage_b),
                    'c': safe_opc_read(equipment.opc_node_voltage_c)
                },
                'current': {
                    'a': safe_opc_read(equipment.opc_node_current_a),
                    'b': safe_opc_read(equipment.opc_node_current_b),
                    'c': safe_opc_read(equipment.opc_node_current_c)
                }
            }
        else:
            # Gateway não configurado ou não é OPC - retorna None (ZERO SIMULATION)
            power_quality = {
                'voltage': {'a': None, 'b': None, 'c': None},
                'current': {'a': None, 'b': None, 'c': None}
            }
        
        # Calcular desequilíbrio (somente se tiver dados válidos)
        voltages = [power_quality['voltage'][p] for p in ['a', 'b', 'c'] if power_quality['voltage'][p] is not None]
        currents = [power_quality['current'][p] for p in ['a', 'b', 'c'] if power_quality['current'][p] is not None]
        
        if voltages:
            avg_voltage = sum(voltages) / len(voltages)
            voltage_imbalance = max(abs(v - avg_voltage) / avg_voltage * 100 for v in voltages) if avg_voltage > 0 else 0
        else:
            avg_voltage = None
            voltage_imbalance = None
        
        total_current = round(sum(currents), 1) if currents else None
        
        return jsonify({
            'success': True,
            'data': {
                'equipment_id': equipment_id,
                'equipment_name': equipment.name,
                'timestamp': datetime.now().isoformat(),
                'available': bool(voltages or currents),
                'power_quality': power_quality,
                'analysis': {
                    'avg_voltage': round(avg_voltage, 1) if avg_voltage else None,
                    'voltage_imbalance_pct': round(voltage_imbalance, 2) if voltage_imbalance else None,
                    'total_current': total_current
                },
                'alerts': {
                    'voltage_imbalance': voltage_imbalance > 2.0 if voltage_imbalance else False,
                    'low_voltage': any(v < 210 for v in voltages) if voltages else False,
                    'high_voltage': any(v > 230 for v in voltages) if voltages else False
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter qualidade de energia: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
