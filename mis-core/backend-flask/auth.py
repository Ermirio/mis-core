"""
Módulo de Autenticação JWT unificado (Validador)
Verifica o cookie access_token ou cabeçalho Authorization
"""
from functools import wraps
from flask import request, jsonify
import jwt
from decouple import config

# Chave simétrica compartilhada com o Django 
SECRET_KEY = config('JWT_SECRET_KEY', default=config('SECRET_KEY', default='django-insecure-dev-key'))

def jwt_required_cookie(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # 1. Tenta pegar do Header "Authorization: Bearer <token>"
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
        # 2. Tenta pegar do Cookie no domínio
        if not token:
            token = request.cookies.get('access_token')
            
        if not token:
            return jsonify({'error': 'Acesso Negado: Token não fornecido'}), 401
            
        try:
            # SimpleJWT uses 'user_id' in its payload by default
            decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = decoded_payload.get('user_id')
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token Expirado'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token Inválido'}), 401
            
        return f(*args, **kwargs)
        
    return decorated_function
