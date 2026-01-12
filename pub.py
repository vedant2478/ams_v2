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
print(f"Initial pin state: {gpio.read()}\n")


# Track previous state to detect changes
previous_state = gpio.read()


# Keep running with polling
try:
    print("Press Ctrl+C to exit\n")
    while True:
        current_state = gpio.read()
        
        # Display current state continuously
        print(f"Pin {GPIO_PIN} state: {current_state}", end='\r')
        
        # Detect state change and publish
        if current_state != previous_state:
            client.publish(MQTT_TOPIC, str(current_state), qos=1)
            status = "OPEN" if current_state == 1 else "CLOSED"
            print(f"\n📢 Door {status} (state={current_state})")
            previous_state = current_state
        
        time.sleep(0.1)  # Poll every 100ms
        
except KeyboardInterrupt:
    print("\n\nStopping...")
    client.disconnect()
    print("✓ Cleanup completed")
