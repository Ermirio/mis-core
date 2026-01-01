# backend/src/routes/hierarchy_routes.py
from flask import Blueprint, request, jsonify
from src.models.hierarchy_model import Hierarchy
from src.models.user import db

hierarchy_bp = Blueprint('hierarchy', __name__)

@hierarchy_bp.route('/hierarchy', methods=['GET'])
def get_hierarchy():
    """Retorna toda a hierarquia (flat list ou tree)"""
    # Por enquanto retorna flat list, o frontend pode montar a árvore
    nodes = Hierarchy.query.all()
    return jsonify({
        'success': True,
        'data': [node.to_dict() for node in nodes]
    })

@hierarchy_bp.route('/hierarchy/tree', methods=['GET'])
def get_hierarchy_tree():
    """Retorna a hierarquia em formato de árvore"""
    roots = Hierarchy.query.filter_by(parent_id=None).all()
    
    def build_tree(node):
        data = node.to_dict()
        
        # Children Hierarchy
        children = Hierarchy.query.filter_by(parent_id=node.id).all()
        tree_children = [build_tree(child) for child in children]
        
        # Equipments (as leaf nodes)
        # Note: We append equipments if they exist. 
        # Using a special 'type' to distinguish.
        for eq in node.equipments:
            tree_children.append({
                'id': f"eq-{eq.id}", # String ID to avoid collision with hierarchy IDs
                'real_id': eq.id,
                'name': eq.name,
                'type': 'equipment',
                'parent_id': node.id,
                'is_equipment': True
            })
            
        if tree_children:
            data['children'] = tree_children
            
        return data

    return jsonify({
        'success': True,
        'data': [build_tree(root) for root in roots]
    })

@hierarchy_bp.route('/hierarchy', methods=['POST'])
def create_node():
    """Cria um novo nó na hierarquia"""
    data = request.get_json()
    print(f"DEBUG: create_node payload: {data}", flush=True)
    
    try:
        new_node = Hierarchy.from_dict(data)
        db.session.add(new_node)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': new_node.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@hierarchy_bp.route('/hierarchy/<int:id>', methods=['PUT'])
def update_node(id):
    """Atualiza um nó existente"""
    node = Hierarchy.query.get_or_404(id)
    data = request.get_json()
    
    try:
        if 'name' in data:
            node.name = data['name']
        if 'code' in data:
            node.code = data['code']
        if 'description' in data:
            node.description = data['description']
        if 'type' in data:
            node.type = data['type']
        if 'parent_id' in data:
            # Evitar ciclos simples (não exaustivo)
            if data['parent_id'] == id:
                return jsonify({'success': False, 'error': 'Nó não pode ser pai de si mesmo'}), 400
            node.parent_id = data['parent_id']
            
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': node.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@hierarchy_bp.route('/hierarchy/<int:id>/delete-info', methods=['GET'])
def get_delete_info(id):
    """Retorna informações sobre o que será excluído"""
    node = Hierarchy.query.get_or_404(id)
    
    def count_children(n):
        """Conta todos os filhos recursivamente"""
        children = Hierarchy.query.filter_by(parent_id=n.id).all()
        total = len(children)
        for child in children:
            total += count_children(child)
        return total
    
    def count_equipments(n):
        """Conta todos os equipamentos neste nó e filhos"""
        total = len(n.equipments) if n.equipments else 0
        children = Hierarchy.query.filter_by(parent_id=n.id).all()
        for child in children:
            total += count_equipments(child)
        return total
    
    children_count = count_children(node)
    equipments_count = count_equipments(node)
    
    type_names = {
        'factory': 'Fábrica',
        'area': 'Área',
        'line': 'Linha',
        'machine_group': 'Grupo de Máquinas'
    }
    
    return jsonify({
        'success': True,
        'data': {
            'id': node.id,
            'name': node.name,
            'type': node.type,
            'type_name': type_names.get(node.type, node.type),
            'children_count': children_count,
            'equipments_count': equipments_count,
            'has_dependencies': children_count > 0 or equipments_count > 0
        }
    })

@hierarchy_bp.route('/hierarchy/<int:id>', methods=['DELETE'])
def delete_node(id):
    """Remove um nó e todos os seus filhos (cascade)"""
    node = Hierarchy.query.get_or_404(id)
    
    # Verificar parâmetro force
    force = request.args.get('force', 'false').lower() == 'true'
    
    def count_all(n):
        """Conta filhos e equipamentos"""
        children = Hierarchy.query.filter_by(parent_id=n.id).all()
        child_count = len(children)
        eq_count = len(n.equipments) if n.equipments else 0
        for child in children:
            cc, ec = count_all(child)
            child_count += cc
            eq_count += ec
        return child_count, eq_count
    
    children_count, equipments_count = count_all(node)
    
    # Se tem dependências e não forçou, retorna erro com informações
    if (children_count > 0 or equipments_count > 0) and not force:
        return jsonify({
            'success': False,
            'error': 'Este nó possui itens dependentes',
            'requires_confirmation': True,
            'details': {
                'children_count': children_count,
                'equipments_count': equipments_count
            }
        }), 400
    
    try:
        def delete_recursive(n):
            """Deleta recursivamente todos os filhos"""
            # Primeiro, desassocia os equipamentos
            for eq in n.equipments:
                eq.hierarchy_id = None
            
            # Depois, deleta os filhos recursivamente
            children = Hierarchy.query.filter_by(parent_id=n.id).all()
            for child in children:
                delete_recursive(child)
            
            # Por fim, deleta o próprio nó
            db.session.delete(n)
        
        delete_recursive(node)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Nó removido com sucesso (filhos: {children_count}, equipamentos desassociados: {equipments_count})'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

