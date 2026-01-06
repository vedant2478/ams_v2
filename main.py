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
from time import sleep

# ================= PATH SETUP =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "reliance_ams_local-master")

if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

# ================= SQLALCHEMY =================
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from csi_ams.utils.commons import SQLALCHEMY_DATABASE_URI

# ================= CAN =================
from amscan import AMS_CAN

# ================= COMPONENTS =================
from components.header.header import Header
from components.footer.footer import Footer
from components.keypad.keypad import Keypad

# ================= LOAD KVs =================
Builder.load_file(os.path.join(BASE_DIR, "components/header/header.kv"))
Builder.load_file(os.path.join(BASE_DIR, "components/footer/footer.kv"))
Builder.load_file(os.path.join(BASE_DIR, "components/keypad/keypad.kv"))

Builder.load_file(os.path.join(BASE_DIR, "pages/home/home.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/auth/auth.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/card_scan/card_scan.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/pin/pin.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/activity/activity.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/key_dashboard/key_dashboard.kv"))
Builder.load_file(os.path.join(BASE_DIR, "pages/activity_done/activity_done.kv"))
Builder.load_file(
    os.path.join(BASE_DIR, "pages/admin_pages/admin_home/admin_home.kv")
)

# ================= SCREENS =================
from pages.home.home import HomeScreen
from pages.auth.auth import AuthScreen
from pages.card_scan.card_scan import CardScanScreen
from pages.pin.pin import PinScreen
from pages.activity.activity import ActivityCodeScreen
from pages.key_dashboard.key_dashboard import KeyDashboardScreen
from pages.activity_done.activity_done import ActivityDoneScreen
from pages.admin_pages.admin_home.admin_home import AdminScreen


class MainApp(App):
    def build(self):
        # ---------- DB ----------
        engine = create_engine(
            SQLALCHEMY_DATABASE_URI,
            connect_args={"check_same_thread": False},
        )
        Session = sessionmaker(bind=engine)
        db_session = Session()

        # ---------- Screen Manager ----------
        sm = ScreenManager(transition=NoTransition())
        sm.db_session = db_session

        # ---------- Shared State ----------
        sm.auth_mode = None
        sm.final_auth_mode = None
        sm.ams_access_log = None

        sm.user_auth = None
        sm.card_info = None
        sm.activity_info = None

        # ---------- CAN INIT (ONCE) ----------
        print("[MAIN] Initializing AMS_CAN...")
        sm.ams_can = AMS_CAN()

        sleep(4)  # allow INIT handshake
        print("[MAIN] AMS_CAN id:", id(sm.ams_can))
        print("[MAIN] Keylists discovered:", sm.ams_can.key_lists)

        # ---------- Screens ----------
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(AuthScreen(name="auth"))
        sm.add_widget(CardScanScreen(name="card_scan"))
        sm.add_widget(PinScreen(name="pin"))
        sm.add_widget(ActivityCodeScreen(name="activity"))
        sm.add_widget(KeyDashboardScreen(name="key_dashboard"))
        sm.add_widget(ActivityDoneScreen(name="activity_done"))
        sm.add_widget(AdminScreen(name="admin_home"))

        sm.current = "home"
        return sm

    def on_stop(self):
        try:
            self.root.db_session.close()
        except Exception:
            pass


if __name__ == "__main__":
    MainApp().run()
