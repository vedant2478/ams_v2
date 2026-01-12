#!/usr/bin/env python3
import time
import mraa
import paho.mqtt.client as mqtt

# Config
GPIO_PIN = 32
MQTT_TOPIC = "gpio/pin32"

# MQTT
client = mqtt.Client("door-publisher-mraa")
client.connect("localhost", 1883, 60)
client.loop_start()

# GPIO with MRAA
gpio = mraa.Gpio(GPIO_PIN)
gpio.dir(mraa.DIR_IN)

print(f"✓ Monitoring GPIO pin {GPIO_PIN}")

# Callback function for GPIO interrupt
def gpio_callback(args):
    state = gpio.read()
    client.publish(MQTT_TOPIC, str(state), qos=1)
    status = "OPEN" if state == 1 else "CLOSED"
    print(f"📢 Door {status} (state={state})")

# Setup interrupt on both edges
gpio.isr(mraa.EDGE_BOTH, gpio_callback, None)

# Keep running
try:
    print("Press Ctrl+C to exit\n")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping...")
    gpio.isrExit()
    client.disconnect()
    print("✓ Cleanup completed")
