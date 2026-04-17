from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty
from kivy.clock import Clock


class Footer(BoxLayout):
    """
    Application footer bar.

    Accepts either:
        version: "12.9.3"       ← preferred
        version_text: "..."     ← legacy alias (screens that used old name)
    """

    version = StringProperty("1.0.0")

    # Legacy alias — any KV that sets version_text will update version
    version_text = StringProperty("")

    def on_version_text(self, instance, value):
        """Sync legacy version_text → version property."""
        if value:
            # Strip a leading "Version: " prefix if present
            cleaned = value.replace("Version: ", "").replace("version:", "").strip()
            if cleaned:
                self.version = cleaned
