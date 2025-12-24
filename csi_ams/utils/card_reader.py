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

def get_card_no(ser):
    ser.close()
    ser.open()
    card_no = 0
    try:
        cnt = 0
        while True:
            sleep(0.1)
            cnt += 1
            print('reading')
            x = ser.readline()
            x = x.decode()
            if x[:2] == "ID":
                card_no = x[3:]
                print(f'card number is: {card_no}')
                break
            if cnt >= 300:
                break
            
    except Exception as e:
        print(e)
    return card_no
            

if __name__ == "__main__":
    while True:
        get_card_no(ser)
    