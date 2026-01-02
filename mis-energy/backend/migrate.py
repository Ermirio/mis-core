import sys
import os
from sqlalchemy import text

# Add current directory to path so imports work
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from src.main_backend import app, db

def run_migration():
    print("Starting migration...")
    with app.app_context():
        try:
            # Check if column exists
            # For MySQL
            conn = db.session.connection()
            result = conn.execute(text("SHOW COLUMNS FROM equipments LIKE 'is_entry_point'"))
            if result.fetchone():
                print("Column 'is_entry_point' already exists.")
            else:
                print("Adding 'is_entry_point' column...")
                conn.execute(text("ALTER TABLE equipments ADD COLUMN is_entry_point BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("Column added successfully.")
        except Exception as e:
            print(f"Migration failed: {e}")
            # Try SQLite syntax if MySQL fails just in case (though config says MySQL)
            try:
                print("Trying generic/SQLite syntax...")
                conn.execute(text("ALTER TABLE equipments ADD COLUMN is_entry_point BOOLEAN DEFAULT 0"))
                db.session.commit()
                print("Column added via fallback.")
            except Exception as e2:
                print(f"Fallback failed: {e2}")

if __name__ == "__main__":
    run_migration()
