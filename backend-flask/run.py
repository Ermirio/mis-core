"""
MIS Flask Application Entry Point
Starts the Flask API Gateway for production data routing.
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
