#!/usr/bin/env python3
import mraa
import time

buzzer = mraa.Gpio(37)
rl1 = mraa.Gpio(38)
rl2 = mraa.Gpio(40)


buzzer.dir(mraa.DIR_OUT)
rl1.dir(mraa.DIR_OUT)
rl2.dir(mraa.DIR_OUT)

rl1.write(1)