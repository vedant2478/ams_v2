# ================= WINDOW CONFIG (MUST BE FIRST) =================
from kivy.config import Config

Config.set("graphics", "fullscreen", "auto")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "borderless", "1")

# ================= SAFE TO IMPORT KIVY NOW =================
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, NoTransition
import os
import sys

# ================= PATH SETUP =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "reliance_ams_local-master")

if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# ================= SQLALCHEMY IMPORTS =================
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from csi_ams.utils.commons import SQLALCHEMY_DATABASE_URI

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
        # -------------------------------------------------
        # 1️⃣ CREATE DATABASE SESSION (ONCE)
        # -------------------------------------------------
        engine = create_engine(
            SQLALCHEMY_DATABASE_URI,
            connect_args={"check_same_thread": False}
        )
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # -------------------------------------------------
        # 2️⃣ SCREEN MANAGER
        # -------------------------------------------------
        sm = ScreenManager(transition=NoTransition())

        # -------------------------------------------------
        # 3️⃣ GLOBAL SHARED STATE (ACCESSIBLE IN ALL SCREENS)
        # -------------------------------------------------
        sm.db_session = db_session        # SQLAlchemy session

        # Authentication state
        sm.auth_mode = None               # 1 = PIN, 2 = CARD, 3 = BIOMETRIC
        sm.final_auth_mode = None         # "PIN", "CARD", "BIOMETRIC"

        # User & logging state
        sm.user_id = None
        sm.access_log_id = None

        # Card info
        sm.card_number = None
        sm.card_info = None

        # -------------------------------------------------
        # 4️⃣ REGISTER SCREENS
        # -------------------------------------------------
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(AuthScreen(name="auth"))
        sm.add_widget(CardScanScreen(name="card_scan"))
        sm.add_widget(PinScreen(name="pin"))
        sm.add_widget(ActivityCodeScreen(name="activity"))
        sm.add_widget(KeyDashboardScreen(name="key_dashboard"))
        sm.add_widget(ActivityDoneScreen(name="activity_done"))

        # -------------------------------------------------
        # 5️⃣ INITIAL SCREEN
        # -------------------------------------------------
        sm.current = "home"
        return sm

    def on_stop(self):
        """
        Gracefully close DB session on app exit
        """
        try:
            self.root.db_session.close()
        except Exception:
            pass


# ================= RUN APP =================
if __name__ == "__main__":
    MainApp().run()


# ================= CAN HELPERS (REFERENCE) =================
# sudo ip link set can0 down
# sudo ip link set can0 type can bitrate 125000 restart-ms 100
# sudo ip link set can0 up
