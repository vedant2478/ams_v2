import mraa
import time


SOL = mraa.Gpio(40)
SOL.dir(mraa.DIR_OUT)


try:
    while True:
        print("Activating solenoid...")
        SOL.write(1)
        time.sleep(2)
        print("Deactivating solenoid...")
        SOL.write(0)
        time.sleep(2)
except KeyboardInterrupt:
    SOL.write(0)
