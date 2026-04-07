import can
from time import sleep

CAN_IMX_ID = 0xFE
strip_id = 1
position = 0 # slot 1

def create_arbitration_id(source, destination, message_type, function):
    arbitration_id = 0x0
    arbitration_id |= (source & 0xFF) << 20
    arbitration_id |= (destination & 0xFF) << 12
    arbitration_id |= (message_type & 0x7) << 9
    arbitration_id |= function & 0x1FF
    return arbitration_id

bus = can.Bus(channel="can0", bustype="socketcan", bitrate=125000)

print("Starting deep CAN parameter test...")

functions = {
    "KEY_ID (0x040)": 0x040,
    "KEY_TAKEN (0x080)": 0x080,
    "KEY_INSERTED (0x100)": 0x100,
    "UNIQUE_ID (0x00E)": 0x00E
}

for name, base_func in functions.items():
    func = base_func | position
    print(f"\nTesting {name} with standard data GET...")
    arb_id = create_arbitration_id(CAN_IMX_ID, strip_id, 2, func) # 2 = GET
    msg = can.Message(arbitration_id=arb_id, data=[], is_extended_id=True)
    bus.send(msg)
    
    timeout = 10
    recv_data = False
    while timeout > 0:
        m = bus.recv(0.1)
        if m:
            print(f"  [RECV] ID:{hex(m.arbitration_id)} DL:{m.dlc} Data:{m.data.hex()}")
            if m.dlc > 0:
                recv_data = True
                break
        timeout -= 1
        
    if not recv_data:
        print("  ❌ No data received.")

print("\nTesting KEY_ID (0x040) with RTR (Remote Transmission Request) frame...")
arb_id = create_arbitration_id(CAN_IMX_ID, strip_id, 2, 0x040 | position)
msg = can.Message(arbitration_id=arb_id, is_remote_frame=True, dlc=5, is_extended_id=True)
bus.send(msg)

timeout = 10
recv_data = False
while timeout > 0:
    m = bus.recv(0.1)
    if m:
        print(f"  [RECV RTR] ID:{hex(m.arbitration_id)} DL:{m.dlc} Data:{m.data.hex()}")
        if m.dlc > 0:
            recv_data = True
            break
    timeout -= 1

if not recv_data:
    print("  ❌ No data received for RTR.")

bus.shutdown()
print("\nDone.")
