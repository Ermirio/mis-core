import requests
import datetime
import time

# Params
INFLUX_URL = "http://influxdb:8086/write?db=industrial_db"
API_BASE = "http://localhost:5005/api"
AUTH = ('admin', 'admin123')
EQ_NAME = "KPI_TEST_EQ"

# 1. Create Test Equipment
print(f"Creating Test Equipment: {EQ_NAME}...")
eq_payload = {
    "name": EQ_NAME,
    "meter_type": "production",
    "equipment_type": "production_meter",
    "gateway_id": None, # No gateway needed for dashboard logic (it uses Influx data)
    "is_active": True
}
# We need to find a way to make sure it has the TAG we want.
# Equipment creation uses logic: `tag = f"{prefix}-{seq:03d}"` if not provided.
# But `dashboard-summary` queries `tag OR name`.
# So if we rely on name, it works.

try:
    # Check if exists first
    res = requests.get(f"{API_BASE}/equipments")
    if res.status_code == 200:
        existing = next((e for e in res.json().get('data', []) if e['name'] == EQ_NAME), None)
        if existing:
            print(f"Equipment {EQ_NAME} already exists (ID: {existing['id']})")
    
    if not existing:
        res_create = requests.post(f"{API_BASE}/equipments", json=eq_payload)
        if res_create.status_code == 201:
            print("Equipment Created!")
        else:
            print(f"Failed to create equipment: {res_create.text}")
            exit(1)
except Exception as e:
    print(f"Error managing equipment: {e}")
    exit(1)

# 2. Inject Data
print("Injecting Dummy Data...")
now = datetime.datetime.now(datetime.timezone.utc)
start_time = now - datetime.timedelta(hours=2)

data_points = []
tag_escaped = EQ_NAME.replace(' ', '\\ ')

for i in range(120): # 2 hours
    ts = int((start_time + datetime.timedelta(minutes=i)).timestamp() * 1e9)
    # Power: 100 kW
    data_points.append(f"energy_consumption,metric=power_kw,tag={tag_escaped} value=100 {ts}")
    # Production Rate: 10 Ton/h
    data_points.append(f"energy_consumption,metric=production_rate,tag={tag_escaped} value=10 {ts}")

payload = "\n".join(data_points)

try:
    response = requests.post(INFLUX_URL, auth=AUTH, data=payload)
    if response.status_code == 204:
        print("Injection Successful!")
    else:
        print(f"Injection Failed: {response.status_code} {response.text}")
        exit(1)
except Exception as e:
    print(f"Connection Error to Influx: {e}")
    exit(1)

# Dump specific data
q_dump = f"SELECT * FROM energy_consumption WHERE \"tag\" = '{EQ_NAME}' LIMIT 5"
res_dump = requests.get(f"http://influxdb:8086/query", params={'db': 'industrial_db', 'q': q_dump, 'u': 'admin', 'p': 'admin123'})
print(f"DEBUG INFLUX DUMP ({EQ_NAME}): {res_dump.json()}")

# AGGREGATION TEST
q_agg = f"SELECT mean(\"value\") FROM \"energy_consumption\" WHERE (\"metric\" = 'power_kw') AND (\"tag\" = '{EQ_NAME}') AND time >= '{start_time.isoformat().replace('+00:00', 'Z')}' AND time <= '{now.isoformat().replace('+00:00', 'Z')}' GROUP BY \"tag\""
print(f"DEBUG AGG QUERY: {q_agg}")
res_agg = requests.get(f"http://influxdb:8086/query", params={'db': 'industrial_db', 'q': q_agg, 'u': 'admin', 'p': 'admin123'})
print(f"DEBUG AGG RESULT: {res_agg.json()}")

# 3. Call API
print("Calling API...")
formatted_start = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
formatted_end = now.strftime('%Y-%m-%dT%H:%M:%SZ')

try:
    res = requests.get(f"{API_BASE}/analytics/dashboard-summary?start_date={formatted_start}&end_date={formatted_end}")
    if res.status_code == 200:
        data = res.json()
        
        curr = data['data']['current']
        curr_ton = curr.get('production_ton')
        curr_kwh = curr.get('consumption_kwh')
        eff = curr.get('efficiency_kwh_ton')
        
        print(f"DEBUG: curr_kwh={curr_kwh}, curr_ton={curr_ton}")
        print(f"Calculated Efficiency: {eff} kWh/Ton")
        
        # Expected: 100 kW / 10 Ton/h = 10 kWh/Ton
        # Note: API averages all active equipments. 
        # If there are OTHER active equipments with 0 data, they might dilute the average or sum?
        # Logic: 
        # q_power_curr = SELECT mean("value") ... GROUP BY "tag"
        # _calculate_energy sums (mean * hours) for EACH tag.
        # So other equipments with NO data (empty series) won't contribute (count=0).
        # So it should be correct.
        
        if 9.0 <= eff <= 11.0:
             print("SUCCESS: Efficiency is correct (approx 10)!")
        else:
             print("FAILURE: Efficiency is incorrect.")
    else:
        print(f"API Failed: {res.status_code} {res.text}")

except Exception as e:
    print(f"Connection Error to API: {e}")
