# ================= WINDOW CONFIG (MUST BE FIRST) =================
from kivy.config import Config


Config.set("graphics", "fullscreen", "auto")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "borderless", "1")

# ================= SAFE TO IMPORT KIVY NOW =================
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, NoTransition
import os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "reliance_ams_local-master")
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# ================= BASE DIR =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= COMPONENT IMPORTS =================
from components.header.header import Header
from components.footer.footer import Footer
from components.keypad.keypad import Keypad

# ================= LOAD COMPONENT KVs =================
Builder.load_file(os.path.join(BASE_DIR, "components/header/header.kv"))
Builder.load_file(os.path.join(BASE_DIR, "components/footer/footer.kv"))
Builder.load_file(os.path.join(BASE_DIR, "components/keypad/keypad.kv"))

# ================= LOAD SCREEN KVs =================
Builder.load_file(os.path.join(BASE_DIR, "pages/home/home.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/auth/auth.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/card_scan/card_scan.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/pin/pin.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/activity/activity.kv"))  
Builder.load_file(os.path.join(BASE_DIR, "pages/key_dashboard/key_dashboard.kv"))  
Builder.load_file(os.path.join(BASE_DIR, "pages/activity_done/activity_done.kv"))

# ================= SCREEN PY IMPORTS =================
from pages.home.home import HomeScreen
from pages.auth.auth import AuthScreen
from pages.card_scan.card_scan import CardScanScreen
from pages.pin.pin import PinScreen
from pages.activity.activity import ActivityCodeScreen
from pages.key_dashboard.key_dashboard import KeyDashboardScreen     
from pages.activity_done.activity_done import ActivityDoneScreen

# ================= MAIN APP =================
class MainApp(App):
    """
    Main application class.
    """

    def build(self):
        sm = ScreenManager(transition=NoTransition())

        # Register screens
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(AuthScreen(name="auth"))
        sm.add_widget(CardScanScreen(name="card_scan"))
        sm.add_widget(PinScreen(name="pin"))
        sm.add_widget(ActivityCodeScreen(name="activity"))
        sm.add_widget(KeyDashboardScreen(name="key_dashboard")) 
        sm.add_widget(ActivityDoneScreen(name = "activity_done"))

        # Initial screen
        sm.current = "home"
        return sm

# ================= RUN APP =================
if __name__ == "__main__":
    MainApp().run()


# sudo ip link set can0 down
# sudo ip link set can0 type can bitrate 125000 restart-ms 100
# sudo ip link set can0 up
