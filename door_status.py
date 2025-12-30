#!/usr/bin/env python3
import time
import mraa

# 🔴 CHANGE THIS PIN IF NEEDED
LIMIT_SWITCH_PIN = 36   # example GPIOH_8 (adjust if required)

try:
    limit_switch = mraa.Gpio(LIMIT_SWITCH_PIN)
    limit_switch.dir(mraa.DIR_IN)
except Exception as e:
    print("-1", flush=True)
    raise SystemExit(1)

# Convention:
# 1 = DOOR OPEN
# 0 = DOOR CLOSED

last_state = None

while True:
    try:
        val = limit_switch.read()
    except Exception:
        val = -1

    # Print ONLY when value changes
    if val != last_state:
        print(val, flush=True)
        last_state = val

    time.sleep(0.1)
