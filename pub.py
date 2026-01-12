#!/usr/bin/env python3
"""
Door Latch Monitor - MRAA + MQTT
Monitors GPIO using MRAA library and publishes to MQTT
"""

import time
import mraa
import paho.mqtt.client as mqtt

# =========================================================
# CONFIGURATION
# =========================================================
GPIO_PIN = 32  # Physical pin number
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "gpio/pin32"
MQTT_CLIENT_ID = "door-publisher-mraa"

# =========================================================
# SETUP MQTT
# =========================================================
client = mqtt.Client(MQTT_CLIENT_ID)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("? Connected to MQTT broker")
    else:
        print(f"? Connection failed: {rc}")

client.on_connect = on_connect
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()

# =========================================================
# SETUP GPIO (MRAA)
# =========================================================
# Initialize GPIO pin as input
gpio = mraa.Gpio(GPIO_PIN)
gpio.dir(mraa.DIR_IN)

print(f"? Monitoring GPIO pin {GPIO_PIN} using MRAA")
print(f"? Publishing to topic: {MQTT_TOPIC}")
print("Press Ctrl+C to exit\n")

# =========================================================
# MAIN LOOP
# =========================================================
last_state = None

try:
    while True:
        # Read GPIO pin state
        state = gpio.read()
        
        # Publish if state changed
        if state != last_state:
            client.publish(MQTT_TOPIC, str(state), qos=1, retain=True)
            status = "OPEN" if state == 1 else "CLOSED"
            print(f"?? Door {status} (state={state})")
            last_state = state
        
        time.sleep(0.1)  # Poll every 100ms
        
except KeyboardInterrupt:
    print("\n\nStopping...")
    client.disconnect()
    print("? MQTT disconnected")
    print("? Cleanup complete")

