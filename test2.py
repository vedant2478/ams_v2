#!/usr/bin/env python3
import sys
import time
import gpiod

GPIOCHIP = "gpiochip0"

BUZZER_LINE = 38
RL1_LINE    = 39
RL2_LINE    = 40

chip = gpiod.Chip(GPIOCHIP)

buzzer = chip.get_line(BUZZER_LINE)
rl1    = chip.get_line(RL1_LINE)
rl2    = chip.get_line(RL2_LINE)

buzzer.request(
    consumer="buzzer",
    type=gpiod.LINE_REQ_DIR_OUT,
    default_val=0
)

rl1.request(
    consumer="relay1",
    type=gpiod.LINE_REQ_DIR_OUT,
    default_val=0
)

rl2.request(
    consumer="relay2",
    type=gpiod.LINE_REQ_DIR_OUT,
    default_val=0
)

# -------- ARGUMENT CHECK --------
if len(sys.argv) != 2:
    print("Usage: python3 solenoid.py <0|1>")
    sys.exit(1)

state = int(sys.argv[1])

# -------- ACTION --------
if state == 1:
    print("[GPIO] Activating solenoids")
    rl1.set_value(1)
    rl2.set_value(1)
    buzzer.set_value(1)
else:
    print("[GPIO] Deactivating solenoids")
    rl1.set_value(0)
    rl2.set_value(0)
    buzzer.set_value(0)

time.sleep(0.2)

buzzer.release()
rl1.release()
rl2.release()
chip.close()
