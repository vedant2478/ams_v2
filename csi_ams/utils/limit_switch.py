import mraa
from time import sleep
import time

LIMIT_SWITCH = mraa.Gpio(32)
LIMIT_SWITCH.dir(mraa.DIR_IN)


while True:
    data = LIMIT_SWITCH.read()
    if data is not None:
        print(f"limit switch status is: {data}")
        sleep(1)
