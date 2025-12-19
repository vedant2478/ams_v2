#!/bin/sh
echo 117 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio117/direction
#hwclock --hctosys --rtc /dev/rtc1


python3 /home/ams-core/main-csi.py &
python3 /home/ams-core/apicalls.py &
python3 /home/ams-core/emdoor.py


cd /bin/Linux_armhf/Activation
./run_pgd.sh start

