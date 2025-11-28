from influxdb import InfluxDBClient

# Conectar ao InfluxDB
client = InfluxDBClient(
    host='127.0.0.1',
    port=8086,
    database='industrial_db',
    username='admin',
    password='admin123'
)

# Buscar OPs distintas
result = client.query('SHOW TAG VALUES FROM producao WITH KEY = "ordem_producao"')
values = list(result.get_points())
ops = [v['value'] for v in values if v['value'] and v['value'] != '']

print(f'\n✅ OPs encontradas no InfluxDB: {len(ops)}\n')
for i, op in enumerate(ops[:10], 1):
    print(f'{i}. {op}')

if len(ops) > 10:
    print(f'\n... e mais {len(ops) - 10} OPs\n')

client.close()
