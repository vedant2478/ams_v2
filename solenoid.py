#!/usr/bin/env python3
import sys
import mraa
import time

# ---------------- GPIO SETUP ----------------
BUZZER_PIN = 37
RL1_PIN = 38
RL2_PIN = 40

buzzer = mraa.Gpio(BUZZER_PIN)
rl1 = mraa.Gpio(RL1_PIN)
rl2 = mraa.Gpio(RL2_PIN)

buzzer.dir(mraa.DIR_OUT)
rl1.dir(mraa.DIR_OUT)
rl2.dir(mraa.DIR_OUT)

# ---------------- ARGUMENT CHECK ----------------
if len(sys.argv) != 2:
    print("Usage: sudo python3 solenoid.py <0|1>")
    sys.exit(1)

try:
    state = int(sys.argv[1])
    if state not in (0, 1):
        raise ValueError
except ValueError:
    print("Invalid argument. Use 1 to ON, 0 to OFF.")
    sys.exit(1)

# ---------------- ACTION ----------------
if state == 1:
    print("[GPIO] Activating solenoids")
    rl1.write(1)
    rl2.write(1)
    
else:
    print("[GPIO] Deactivating solenoids")
    rl1.write(0)
    rl2.write(0)
  

time.sleep(0.2)
