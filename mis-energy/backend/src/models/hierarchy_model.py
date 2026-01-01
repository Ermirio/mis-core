# backend/src/models/hierarchy_model.py
from src.models.user import db
from datetime import datetime

class Hierarchy(db.Model):
    """Modelo para hierarquia da fábrica (Fábrica -> Área -> Linha -> Máquina)"""
    __tablename__ = 'hierarchies'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=True) # Código para tag (ex: FAC1, LIN2)
    type = db.Column(db.String(50), nullable=False)  # factory, area, line, machine_group
    description = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('hierarchies.id'), nullable=True)
    
    # Metadados
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento recursivo (filhos)
    children = db.relationship('Hierarchy', 
                             backref=db.backref('parent', remote_side=[id]),
                             lazy='dynamic')
    
    # Relacionamento com equipamentos
    equipments = db.relationship('Equipment', backref='hierarchy', lazy=True)
    
    def __repr__(self):
        return f'<Hierarchy {self.name} ({self.type})>'
    
    def to_dict(self):
        """Converte o modelo para dicionário"""
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'type': self.type,
            'description': self.description,
            'parent_id': self.parent_id,
            'parent_name': self.parent.name if self.parent else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data):
        """Cria instância a partir de dicionário"""
        return cls(
            name=data.get('name'),
            code=data.get('code'),
            type=data.get('type'),
            description=data.get('description'),
            parent_id=data.get('parent_id')
        )
