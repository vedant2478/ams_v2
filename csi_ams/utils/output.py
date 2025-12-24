import mraa
import time


# BUZZ = mraa.Gpio(37)
# RL1 = mraa.Gpio(10) # 38
# RL2 = mraa.Gpio(40)
LS = mraa.Gpio(7)

# set gpio as outputs
# BUZZ.dir(mraa.DIR_OUT)
# RL1.dir(mraa.DIR_OUT)
# RL2.dir(mraa.DIR_OUT)
LS.dir(mraa.DIR_IN)

# toggle both gpio's
while True:
    # BUZZ.write(1)
    # RL1.write(1)
    # RL2.write(1)
    print(f'limit switch: {LS.read()}')

    time.sleep(1)

    # BUZZ.write(0)
    # RL1.write(0)
    # RL2.write(0)

    time.sleep(1)
