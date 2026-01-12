#!/usr/bin/env python3
import time
import mraa
import paho.mqtt.client as mqtt
from queue import Queue


# Config
GPIO_PIN = 32
MQTT_TOPIC = "gpio/pin32"
event_queue = Queue()


# MQTT
client = mqtt.Client("door-publisher-mraa")
client.connect("localhost", 1883, 60)
client.loop_start()


# GPIO with MRAA
gpio = mraa.Gpio(GPIO_PIN)
gpio.dir(mraa.DIR_IN)


print(f"✓ Monitoring GPIO pin {GPIO_PIN}")


# Callback function for GPIO interrupt
def gpio_callback(gpio_obj):
    state = gpio_obj.read()
    event_queue.put(state)


# Setup interrupt on both edges
gpio.isr(mraa.EDGE_BOTH, gpio_callback, gpio)


# Keep running
try:
    print("Press Ctrl+C to exit\n")
    while True:
        if not event_queue.empty():
            state = event_queue.get()
            client.publish(MQTT_TOPIC, str(state), qos=1)
            status = "OPEN" if state == 1 else "CLOSED"
            print(f"📢 Door {status} (state={state})")
        time.sleep(0.01)
except KeyboardInterrupt:
    print("\nStopping...")
    gpio.isrExit()
    client.disconnect()
    print("✓ Cleanup completed")
