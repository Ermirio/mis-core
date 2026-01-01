# backend/init_db.py
import os
import sys

# Adicionar diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.main_backend import app, db

def init_db():
    print("Initializing database...")
    with app.app_context():
        try:
            # Tentar criar tabelas
            db.create_all()
            print("Tables created successfully.")
        except Exception as e:
            print(f"Error creating tables: {e}")

if __name__ == "__main__":
    init_db()
