from src.models.user import db
from flask import Flask
from src.config import Config
import pymysql

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

def update_schema():
    with app.app_context():
        engine = db.engine
        with engine.connect() as conn:
            # Add tag to equipments
            try:
                conn.execute(db.text("ALTER TABLE equipments ADD COLUMN tag VARCHAR(50) UNIQUE"))
                print("Added tag column to equipments")
            except Exception as e:
                print(f"Error adding tag column: {e}")

            # Add code to hierarchies
            try:
                conn.execute(db.text("ALTER TABLE hierarchies ADD COLUMN code VARCHAR(20)"))
                print("Added code column to hierarchies")
            except Exception as e:
                print(f"Error adding code column: {e}")
                
            conn.commit()

if __name__ == '__main__':
    update_schema()
