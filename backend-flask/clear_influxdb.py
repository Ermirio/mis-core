"""
Script to clear and recreate InfluxDB database
"""
from influxdb import InfluxDBClient
from decouple import config

# InfluxDB configuration
INFLUX_HOST = config('INFLUXDB_HOST', default='127.0.0.1')
INFLUX_PORT = config('INFLUXDB_PORT', default=8086, cast=int)
INFLUX_DB = config('INFLUXDB_DATABASE', default='industrial_db')
INFLUX_USER = config('INFLUXDB_USER', default=None)
INFLUX_PASS = config('INFLUXDB_USER_PASSWORD', default=None)

print("=" * 80)
print("CLEARING INFLUXDB DATABASE")
print("=" * 80)

try:
    # Connect to InfluxDB
    client = InfluxDBClient(
        host=INFLUX_HOST,
        port=INFLUX_PORT,
        username=INFLUX_USER,
        password=INFLUX_PASS
    )
    
    print(f"\n✓ Connected to InfluxDB at {INFLUX_HOST}:{INFLUX_PORT}")
    
    # List existing databases
    databases = client.get_list_database()
    print(f"\nExisting databases: {[db['name'] for db in databases]}")
    
    # Drop database if exists
    if any(db['name'] == INFLUX_DB for db in databases):
        print(f"\n⚠ Dropping database '{INFLUX_DB}'...")
        client.drop_database(INFLUX_DB)
        print(f"✓ Database '{INFLUX_DB}' dropped")
    else:
        print(f"\nℹ Database '{INFLUX_DB}' does not exist")
    
    # Create database
    print(f"\n✓ Creating database '{INFLUX_DB}'...")
    client.create_database(INFLUX_DB)
    print(f"✓ Database '{INFLUX_DB}' created")
    
    # Verify
    databases = client.get_list_database()
    print(f"\nCurrent databases: {[db['name'] for db in databases]}")
    
    print("\n" + "=" * 80)
    print("✓ DATABASE RESET COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Restart Flask backend (py app.py)")
    print("2. Restart coletor (py coletor.py)")
    print("3. Wait 2-3 minutes for data collection")
    print("4. Verify new tag structure")
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
