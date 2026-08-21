"""
Blueprint Registration
Registers all route blueprints with the Flask application.
"""

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    from .ingestion import ingestion_bp
    from .equipment import equipment_bp
    from .production import production_bp
    from .factory import factory_bp
    from .system import system_bp
    
    app.register_blueprint(ingestion_bp)
    app.register_blueprint(equipment_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(factory_bp)
    app.register_blueprint(system_bp)
