from time import sleep
import amsbms
from amsbms import *

def main():
    print("Starting card reading script...")

    while True:
        card_info = amsbms.cardNo
        print("\nCard no is : " + str(card_info))
        sleep(1)


if __name__ == "__main__":
    main()

# cat /etc/systemd/network/eth0.network
# rm /etc/systemd/network/eth0.network
# reboot