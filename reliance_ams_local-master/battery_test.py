import ctypes
from time import sleep

lib_battery = ctypes.CDLL("libBattery.so")
lib_battery.getBatteryPercentage.argtypes = []
lib_battery.bmsInit.argtypes = []
lib_battery.getCardDetails.argtypes = []
lib_battery.getCardDetails.restype = ctypes.c_ulonglong
lib_battery.bmsInit()
sleep(1)


while True:
    BATTERY_CHARGE_PC = lib_battery.getBatteryPercentage()
    print(BATTERY_CHARGE_PC)
    sleep(2)