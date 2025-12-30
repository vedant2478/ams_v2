#!/usr/bin/env python3
import time
import mraa
from csi_ams.utils.commons import LIMIT_SWITCH, read_limit_switch

while True:
    try:
        state = read_limit_switch(LIMIT_SWITCH)
        print(state, flush=True)
    except Exception:
        print(-1, flush=True)

    time.sleep(0.2)
