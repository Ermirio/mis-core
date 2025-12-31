"""
wsgi.py - Corrigido para usar 1 worker apenas
PROBLEMA: Gunicorn com múltiplos workers + asyncio OPC causa conflitos
SOLUÇÃO: Usar apenas 1 worker (preload_app=True não resolve o problema de asyncio)
"""

from app import app

if __name__ == "__main__":
    # Configuração para produção com Gunicorn
    # IMPORTANTE: Use apenas 1 worker devido ao OPC asyncio + threading
    # Comando: gunicorn --workers 1 --bind 0.0.0.0:5004 --timeout 120 wsgi:app
    app.run(host='0.0.0.0', port=5004, debug=True)

