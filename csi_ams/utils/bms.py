import math
import serial
from time import sleep

ser = serial.Serial(
    port="/dev/ttyAML1",  # Replace ttyS0 with ttyAM0 for Pi1,Pi2,Pi0
    baudrate=9600,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=5,
)


def convert_volt_to_pct(value, low_volt=9.7, high_volt=11.1, low_pct=0, high_pct=100):
    leftSpan = high_volt - low_volt
    rightSpan = high_pct - low_pct
    valueScaled = float(value - low_volt) / float(leftSpan)
    return low_pct + (valueScaled * rightSpan)


def get_batt_pct(ser):
    ser.close()
    ser.open()
    batt_volt = 0
    try:
        while True:
            x = ser.readline()
            x = x.decode()
            
            if x[:4] == "BATT":
                batt_volt = float(x[5:10])
                print(batt_volt)
                if batt_volt < 9.7:
                    batt_volt = 9.7
                elif batt_volt > 11.1:
                    batt_volt = 11.1
                batt_volt = math.floor(convert_volt_to_pct(batt_volt))
                print(f'battery percentage is: {batt_volt}')
                break
            
    except Exception as e:
        print(e)
    return batt_volt
            

if __name__ == "__main__":
    while True:
        get_batt_pct(ser)