# backend/update_schema_v2.py
"""
Script para atualizar schema do banco de dados MIS-Energy.
Adiciona colunas faltantes às tabelas existentes.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask
from src.models.user import db
from src.config import Config
import pymysql

def run_migrations():
    """Executa migrations para adicionar colunas faltantes"""
    
    # Conectar diretamente ao MySQL para alterações de schema
    connection = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'mis-hub-mysql'),
        user=os.getenv('MYSQL_USER', 'root'),
        password=os.getenv('MYSQL_PASSWORD', 'mis-root-password'),
        database=os.getenv('MYSQL_DATABASE', 'mis_energy'),
        charset='utf8mb4'
    )
    
    migrations = [
        # Adicionar meter_type ao equipments
        """
        ALTER TABLE equipments 
        ADD COLUMN IF NOT EXISTS meter_type VARCHAR(20) DEFAULT 'energy' NOT NULL
        """,
        
        # Adicionar energy_meter_id ao hierarchies
        """
        ALTER TABLE hierarchies 
        ADD COLUMN IF NOT EXISTS energy_meter_id INT NULL,
        ADD CONSTRAINT fk_hierarchy_energy_meter 
        FOREIGN KEY (energy_meter_id) REFERENCES equipments(id) ON DELETE SET NULL
        """,
        
        # Adicionar production_meter_id ao hierarchies
        """
        ALTER TABLE hierarchies 
        ADD COLUMN IF NOT EXISTS production_meter_id INT NULL,
        ADD CONSTRAINT fk_hierarchy_production_meter 
        FOREIGN KEY (production_meter_id) REFERENCES equipments(id) ON DELETE SET NULL
        """,
        
        # Criar tabela metrics_config se não existir
        """
        CREATE TABLE IF NOT EXISTS metrics_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            kwh_cost_brl FLOAT DEFAULT 0.85 NOT NULL,
            usd_brl_rate FLOAT DEFAULT 5.0 NOT NULL,
            eur_brl_rate FLOAT DEFAULT 5.5 NOT NULL,
            production_unit VARCHAR(20) DEFAULT 'ton' NOT NULL,
            production_unit_label VARCHAR(50) DEFAULT 'Toneladas' NOT NULL,
            simulation_enabled TINYINT(1) DEFAULT 1 NOT NULL,
            updated_at DATETIME,
            updated_by VARCHAR(100)
        )
        """
    ]
    
    try:
        with connection.cursor() as cursor:
            for sql in migrations:
                try:
                    # Limpeza de SQL
                    clean_sql = sql.strip()
                    if clean_sql:
                        print(f"Executando: {clean_sql[:60]}...")
                        cursor.execute(clean_sql)
                        print("  ✓ OK")
                except pymysql.err.OperationalError as e:
                    if "Duplicate column" in str(e) or "Duplicate key" in str(e):
                        print(f"  - Coluna/chave já existe, pulando...")
                    else:
                        print(f"  ✗ Erro: {e}")
                except Exception as e:
                    print(f"  ✗ Erro: {e}")
        
        connection.commit()
        print("\n✓ Migrations concluídas!")
        
    except Exception as e:
        print(f"Erro na conexão: {e}")
        raise
    finally:
        connection.close()

if __name__ == '__main__':
    print("=== MIS-Energy Schema Migration v2 ===\n")
    run_migrations()
