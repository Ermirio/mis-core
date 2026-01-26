import paho.mqtt.client as mqtt
import time
import sys

BROKER = "localhost"
PORT = 1883
TOPIC = "test/verification"

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[SUCCESS] Connected to MQTT Broker!")
        client.subscribe(TOPIC)
    else:
        print(f"[ERROR] Failed to connect, return code {rc}")
        sys.exit(1)

def on_message(client, userdata, msg):
    print(f"[SUCCESS] Received message '{msg.payload.decode()}' on topic '{msg.topic}'")
    sys.exit(0)

# Handle Paho MQTT v2 compatibility
try:
    from paho.mqtt.enums import CallbackAPIVersion
    client = mqtt.Client(CallbackAPIVersion.VERSION2, "verify_script")
except ImportError:
    # Paho v1
    client = mqtt.Client("verify_script")
client.on_connect = on_connect
client.on_message = on_message

print(f"Connecting to {BROKER}:{PORT}...")
try:
    client.connect(BROKER, PORT, 60)
except Exception as e:
    print(f"[ERROR] Could not connect to broker: {e}")
    sys.exit(1)

client.loop_start()
time.sleep(1)
print(f"Publishing to {TOPIC}...")
client.publish(TOPIC, "Hello, EMQX!")

# Wait for message
time.sleep(2)
print("[TIMEOUT] Did not receive message back.")
client.loop_stop()
sys.exit(1)
