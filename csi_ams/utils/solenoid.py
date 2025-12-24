import mraa
import time


SOL = mraa.Gpio(40)
SOL.dir(mraa.DIR_OUT)


try:
    while True:
        SOL.write(1)
        time.sleep(2)
        SOL.write(0)
        time.sleep(2)
except KeyboardInterrupt:
    SOL.write(0)
