import serial
import threading
import time


port = '/dev/ttymxc2'
baud = 9600
vDC = 0
cardNo = 0
batteryPc = 0

serial_port = serial.Serial(port, baud, timeout=120)


def handle_data(data):
    global vDC
    global cardNo
    global batteryPc
    vDC = str(int(data[2:3].hex(), 16))
    batteryPc = str(int(data[3:4].hex(), 16))
    cardNo = str(int(data[5:13].hex(), 16))
    with open('bms.dat', 'w') as fAck:
        fAck.write(vDC + "," + batteryPc + "," + cardNo)
        fAck.close()

def read_from_port(ser):
    connected = False
    while not connected:
        connected = True

        while True:
            size = ser.inWaiting()
            if size == 17:
                data = ser.read(size)
                handle_data(data)
            time.sleep(0.25)


thread = threading.Thread(target=read_from_port, args=(serial_port,))
thread.start()

