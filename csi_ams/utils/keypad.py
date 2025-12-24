#!/usr/bin/env python
import smbus2
import sys
import time

""" this is an example on how to create a keypad using the pcf8475

    I use an old telephone keypad and this is the layout of it


    

            Pin4(P4)  Pin6(P5)   Pin8(P6)
               |         |          |
  Pin5(P0) --- 1 ------- 2 -------- 3
               |         |          |
  Pin7(P1) --- 4 ------- 5 -------- 6
               |         |          |
  Pin2(P2) --- 7 ------- 8 -------- 9
               |         |          |
  Pin3(P3) --- * ------- 0 -------- #
   
  
          

"""


class MyKeyboard:

    KeyPadTable = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["*", "0", "#"]]
    RowID = [0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 3, 0, 2, 1, 0]

    CurrentKey = None

    def __init__(self, I2CBus=3, I2CAddress=0x20):
        self.I2CAddress = I2CAddress
        self.I2CBus = I2CBus
        # open smbus pcf8574
        self.bus = smbus2.SMBus(self.I2CBus)
        # set pcf to input
        self.bus.write_byte(self.I2CAddress, 0xFF)

        # ReadRawKey
        # this function will scan and return a key press
        # with no debouncing.
        # it will return None if no or more than a key is pressed on the same row

    def ReadRawKey(self):
        # set P4 Low First
        OutPin = 0x10
        for Column in range(3):
            # scan first row to see if we have something
            self.bus.write_byte(self.I2CAddress, ~OutPin)
            # read the key now
            key = self.RowID[self.bus.read_byte(self.I2CAddress) & 0x0F]
            if key > 0:
                return self.KeyPadTable[key - 1][Column]
            OutPin = OutPin * 2
        return None

    # ReadKey return current key once and debounce it
    def ReadKey(self):
        LastKey = self.CurrentKey
        while True:
            NewKey = self.ReadRawKey()
            if NewKey != LastKey:
                time.sleep(0.02)
                LastKey = NewKey
            else:
                break
        # if LastValue is the same than CurrentValue
        # just return None
        if LastKey == self.CurrentKey:
            return None
        # ok put Lastvalue to be CurrentValue
        self.CurrentKey = LastKey
        return self.CurrentKey


if __name__ == "__main__":

    test = MyKeyboard()

    while True:

        V = test.ReadKey()
        if V != None:
            print('key pressed is -> ', end='')
            sys.stdout.write(V)
            print()
            sys.stdout.flush()
        else:
            time.sleep(0.001)
