"""
Módulo de Autenticação JWT unificado (Validador para Flask c/ python-dotenv)
Verifica o cookie access_token ou cabeçalho Authorization
"""
from functools import wraps
from flask import request, jsonify
import jwt
import os

# Chave simétrica compartilhada (mesmo secret key do Django/Core)
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', os.environ.get('SECRET_KEY', 'django-insecure-dev-key'))

def jwt_required_cookie(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # 1. Tenta pegar do Header "Authorization: Bearer <token>"
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
        # 2. Tenta pegar do Cookie no domínio (.mis.local)
        if not token:
            token = request.cookies.get('access_token')
            
        if not token:
            return jsonify({'error': 'Acesso Negado: Token não fornecido'}), 401
            
        try:
            # SimpleJWT usa 'user_id' no payload
            decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = decoded_payload.get('user_id')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token Expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token Inválido'}), 401
            
        return f(*args, **kwargs)
        
    return decorated_function
