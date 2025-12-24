import serial
from time import sleep

ser = serial.Serial(
        port='/dev/ttyAML0', #Replace ttyS0 with ttyAM0 for Pi1,Pi2,Pi0
        baudrate = 9600,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=5
)

while True:
        x=ser.readline()
        print(x)

