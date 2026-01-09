from datetime import datetime

from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.clock import Clock

from components.base_screen import BaseScreen
from csi_ams.utils.commons import TZ_INDIA


class ActivityCard(BoxLayout):
    key_name = StringProperty("")
    taken_text = StringProperty("")
    returned_text = StringProperty("")


class ActivityDoneScreen(BaseScreen):
    retrieved_text = StringProperty("")
    returned_text = StringProperty("")
    timestamp_text = StringProperty("")
    countdown = NumericProperty(30)

    # list of dicts: [{"key_name":..., "taken_text":..., "returned_text":...}, ...]
    cards = ListProperty([])

    def on_pre_enter(self, *args):
        # demo data – later you can overwrite from dashboard
        self.cards = self.manager.cards
        self.timestamp_text = self.manager.timestamp_text

        self.populate_cards()

    def on_enter(self, *args):
        self.countdown = 30
        self._event = Clock.schedule_interval(self._tick, 1)

    def on_leave(self, *args):
        if hasattr(self, "_event"):
            self._event.cancel()

    def _tick(self, dt):
        if self.countdown > 0:
            self.countdown -= 1
        if self.countdown == 0 and self.manager:
            self.manager.current = "home"

    def on_return_pressed(self):
        if hasattr(self, "_event"):
            self._event.cancel()
        if self.manager:
            self.manager.current = "home"

    def populate_cards(self):
        container = self.ids.cards_container
        container.clear_widgets()
        for data in self.cards:
            card = ActivityCard(
                key_name=data["key_name"],
                taken_text=data["taken_text"],
                returned_text=data["returned_text"],
            )
            container.add_widget(card)
