# hw_init.py
import sys
import os

# Add backend to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "reliance_ams_local-master")
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# Try to import hardware (will fail on Windows without hardware)
try:
    from amsbms import amsbms
    from consts import KEY_DICT, AUTH_MODE_CARD_PIN, AUTH_MODE_BIO
    print("✓ Real hardware loaded")
    MOCK_MODE = False
except Exception as e:
    print(f"⚠ Hardware not available, using INTERACTIVE mock mode: {e}")
    
    # Mock hardware for development with user input
    class MockAMSBMS:
        def __init__(self):
            self._cardNo = 0
            self._asked = False
        
        @property
        def cardNo(self):
            # Ask user only once per session
            if not self._asked:
                self._asked = True
                print("\n" + "="*50)
                print("🎮 MOCK CARD READER - TESTING MODE")
                print("="*50)
                response = input("Do you want to simulate card scan? (y/n): ").strip().lower()
                
                if response == 'y':
                    card_input = input("Enter card number (or press Enter for default 12345678): ").strip()
                    self._cardNo = int(card_input) if card_input else 12345678
                    print(f"✓ Mock card will be detected: {self._cardNo}")
                else:
                    self._cardNo = 0
                    print("✗ Mock card scan will TIMEOUT")
                print("="*50 + "\n")
            
            return self._cardNo
    
    amsbms = MockAMSBMS()
    
    # Mock constants
    KEY_DICT = {
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
        '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
        'ENTER': 'ENTER', 'CLEAR': 'CLEAR', 'ESC': 'ESC',
        'UP': 'UP', 'DN': 'DN', 'F1': 'F1'
    }
    AUTH_MODE_CARD_PIN = 1
    AUTH_MODE_BIO = 2
    MOCK_MODE = True

# Export
__all__ = ['amsbms', 'KEY_DICT', 'AUTH_MODE_CARD_PIN', 'AUTH_MODE_BIO', 'MOCK_MODE']
