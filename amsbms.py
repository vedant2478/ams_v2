import serial
import time
from datetime import datetime
from threading import Thread, Lock


class AMSBMS:
    def __init__(self, port="/dev/ttyAML1", baud=9600, timeout=1, logfile="bms.dat"):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.logfile = logfile

        self.ser = None
        self.running = False
        self.thread = None
        self.lock = Lock()

        # latest values
        self.cardNo = None
        self.battery_voltage = None
        self.charging_status = None

        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                bytesize=serial.EIGHTBITS,
                timeout=self.timeout
            )
            print(f"✅ Opened {self.port} at {self.baud} baud")
            self.running = True
            self.thread = Thread(target=self._reader, daemon=True)
            self.thread.start()
        except Exception as e:
            print(f"⚠️ Error opening {self.port}: {e}")

    def _parse_message(self, line: str):
        """Parse a single line from BMS."""
        line = line.strip()
        if line.startswith("BATT="):
            return {"type": "battery", "voltage": line.split("=")[1]}
        elif line.startswith("CHARGE"):
            return {"type": "charging", "status": line}
        elif line.startswith("ID="):
            return {"type": "id", "value": line.split("=")[1]}
        else:
            return {"type": "unknown", "raw": line}

    def _reader(self):
        """Background thread to read serial data."""
        while self.running:
            try:
                raw = self.ser.readline()
                if raw:
                    try:
                        line = raw.decode(errors="ignore").strip()
                    except UnicodeDecodeError:
                        line = str(raw)

                    parsed = self._parse_message(line)
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    with self.lock:
                        if parsed["type"] == "battery":
                            self.battery_voltage = parsed["voltage"]
                        elif parsed["type"] == "charging":
                            self.charging_status = parsed["status"]
                        elif parsed["type"] == "id":
                            self.cardNo = parsed["value"]

                    # with open(self.logfile, 'w') as f:
                    #     f.write(f"{self.charging_status or ''},{self.battery_voltage or ''},{self.cardNo or ''}")
                    #     f.close()

            except Exception as e:
                print(f"⚠️ Error reading: {e}")
            time.sleep(0.1)

    def stop(self):
        """Stop background thread and close serial."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        if self.ser:
            self.ser.close()
        print("🔒 Port closed")

    def get_battery_voltage(self):
        with self.lock:
            value = self.battery_voltage
            self.battery_voltage = None
            return value

    def get_charging_status(self):
        with self.lock:
            value = self.charging_status
            self.charging_status = None
            return value

    def get_cardNo(self):
        with self.lock:
            value = self.cardNo
            self.cardNo = None
            return value
