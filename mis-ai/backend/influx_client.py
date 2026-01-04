import os
import logging
from influxdb import InfluxDBClient
from datetime import datetime

class InfluxClient:
    def __init__(self):
        self.host = os.getenv('INFLUXDB_HOST', 'influxdb')
        self.port = int(os.getenv('INFLUXDB_PORT', 8086))
        self.user = os.getenv('INFLUXDB_USER', '')
        self.password = os.getenv('INFLUXDB_PASSWORD', '')
        self.database = os.getenv('INFLUXDB_DATABASE', 'mis-ai')
        self.client = None
        self.connected = False

    def connect(self):
        """Establish connection to InfluxDB"""
        try:
            self.client = InfluxDBClient(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.database
            )
            self.connected = True
            logging.info(f"✅ InfluxDB Client configured for {self.host}:{self.port} (DB: {self.database})")
            return True
        except Exception as e:
            logging.error(f"❌ Failed to configure InfluxDB Client: {e}")
            self.connected = False
            return False

    def check_connection(self):
        """Ping the server"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def create_database(self):
        """Ensure database exists"""
        if not self.client:
            if not self.connect():
                return False
        
        try:
            # Check if database exists
            dbs = self.client.get_list_database()
            if not any(db['name'] == self.database for db in dbs):
                logging.info(f"Creating database {self.database}...")
                self.client.create_database(self.database)
                logging.info(f"✅ Database {self.database} created successfully.")
            else:
                logging.info(f"ℹ️ Database {self.database} already exists.")
            
            # Switch to it
            self.client.switch_database(self.database)
            return True
        except Exception as e:
            logging.error(f"❌ Error ensuring database existence: {e}")
            return False

    def write_point(self, measurement, tags, fields, time=None):
        """Write a single point"""
        if not self.client:
             if not self.connect():
                return False
        
        if time is None:
            time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        json_body = [
            {
                "measurement": measurement,
                "tags": tags,
                "time": time,
                "fields": fields
            }
        ]
        
        try:
            self.client.write_points(json_body)
            return True
        except Exception as e:
            logging.error(f"❌ Error writing to InfluxDB: {e}")
            return False

# Singleton instance
influx_client = InfluxClient()
