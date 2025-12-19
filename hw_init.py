# hw_init.py
import sys
import os
import platform

# Add backend to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "reliance_ams_local-master")
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# Detect if running on actual hardware (Linux with serial port)
IS_HARDWARE = (
    platform.system() == "Linux" and 
    (os.path.exists("/dev/ttyAML1") or os.path.exists("/dev/ttymxc2"))
)

if IS_HARDWARE:
    print("✓ Running on HARDWARE - using real devices")
    try:
        from amsbms import AMSBMS
        from consts import KEY_DICT, AUTH_MODE_CARD_PIN, AUTH_MODE_BIO
        
        # Initialize hardware with correct port
        amsbms = AMSBMS(port="/dev/ttyAML1", baud=9600)
        
        MOCK_MODE = False
        print("✓ Real hardware loaded successfully")
    except Exception as e:
        print(f"✗ Error loading hardware: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
else:
    print(f"⚠ Running on DEVELOPMENT machine ({platform.system()}) - using mock mode")
    
    # Mock hardware for development
    class MockAMSBMS:
        def __init__(self):
            self._cardNo = None
            self._asked = False
        
        @property
        def cardNo(self):
            if not self._asked:
                self._asked = True
                print("\n" + "="*50)
                print("🎮 MOCK CARD READER - TESTING MODE")
                print("="*50)
                response = input("Simulate card scan? (y/n): ").strip().lower()
                
                if response == 'y':
                    card_input = input("Enter card number (default 12345678): ").strip()
                    self._cardNo = card_input if card_input else "12345678"
                    print(f"✓ Mock card: {self._cardNo}")
                else:
                    self._cardNo = None
                    print("✗ Mock timeout")
                print("="*50 + "\n")
            
            return self._cardNo
        
        def get_cardNo(self):
            """Compatibility with AMSBMS interface"""
            return self.cardNo
    
    amsbms = MockAMSBMS()
    
    KEY_DICT = {
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
        '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
        'ENTER': 'ENTER', 'CLEAR': 'CLEAR', 'ESC': 'ESC',
        'UP': 'UP', 'DN': 'DN', 'F1': 'F1'
    }
    AUTH_MODE_CARD_PIN = 1
    AUTH_MODE_BIO = 2
    MOCK_MODE = True

__all__ = ['amsbms', 'KEY_DICT', 'AUTH_MODE_CARD_PIN', 'AUTH_MODE_BIO', 'MOCK_MODE', 'IS_HARDWARE']
