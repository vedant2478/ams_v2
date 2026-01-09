from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.clock import Clock
from kivy.lang import Builder
from components.base_screen import BaseScreen


class ActivityDoneScreen(BaseScreen):
    retrieved_text = StringProperty("")
    returned_text = StringProperty("")
    timestamp_text = StringProperty("")
    countdown = NumericProperty(5)

    # list of dicts for demo
    cards = ListProperty()

    def on_pre_enter(self, *args):
        # demo data
        self.cards = [
            {
                "key_name": "Master Key 1",
                "taken_text": "2025-07-25 14:32:09",
                "returned_text": "2025-07-25 14:59:09",
            },
            {
                "key_name": "Master Key 1",
                "taken_text": "2025-07-25 14:32:09",
                "returned_text": "2025-07-25 14:59:09",
            },
            {
                "key_name": "Master Key 1",
                "taken_text": "2025-07-25 14:32:09",
                "returned_text": "2025-07-25 14:59:09",
            },
        ]
        self.populate_cards()

    def on_enter(self, *args):
        self.countdown = 5
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
            card = Builder.template(
                "ActivityCard",
                key_name=data["key_name"],
                taken_text=data["taken_text"],
                returned_text=data["returned_text"],
            )
            container.add_widget(card)
