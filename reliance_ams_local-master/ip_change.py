import sys
import os
# f = open("/lib/systemd/network/wired.network", "w")
# netmask = '255.255.192.0'

# print('Ip1 address: '+sys.argv[1])
# print('Netmask : '+sys.argv[2])
# print('Gateway :'+sys.argv[3])
netmask = sys.argv[2]
cidr = sum(bin(int(x)).count('1') for x in netmask.split('.'))
f = open("/home/ams-core/wired.network", "w")
f.write("[Match]\n")
f.write("Name=eth0\n")
f.write("[Network]\n")

f.write("Address="+str(sys.argv[1])+"/"+str(cidr))
# f.write("Address="+"192.1.0.2"+"/"+str(cidr))
f.write("\nGateway="+sys.argv[3])
# f.write("\nGateway=")
f.write("\nDNS=8.8.8.8")
f.close()

os.system('chmod +x wired.network')
os.system('scp /home/ams-core/wired.network /lib/systemd/network/')
os.system('scp /home/ams-core/wired.network /etc/systemd/network/')
os.system('mv /etc/systemd/network/wired.network /etc/systemd/network/eth0.network')
#os.system(f'ifconfig eth0 {str(sys.argv[1])} netmask 255.255.255.192')
#os.system(f'route add default gw {str(sys.argv[3])}')
os.system('reboot')
