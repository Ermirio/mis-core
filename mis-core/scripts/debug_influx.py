from influxdb import InfluxDBClient
from decouple import config

host = config('INFLUXDB_HOST', default='localhost')
client = InfluxDBClient(host=host, port=8086, database='mis_core')

rs = client.query("SELECT * FROM production WHERE equipment='E001' ORDER BY time DESC LIMIT 1")
print(list(rs.get_points()))
