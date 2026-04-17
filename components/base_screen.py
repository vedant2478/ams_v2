# components/base_screen.py
"""
Base screen with automatic solid background.
All app screens should inherit from this class.

PERFORMANCE: Using a simple color and rectangle.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle


class SolidBackground(Widget):
    """
    Reusable solid background widget.
    Uses #0F172A (Slate 900) for a slick, dark industrial theme.
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._redraw, size=self._redraw)
        self._rect = None

    def _redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # #0F172A (Slate 900)
            Color(0.059, 0.090, 0.165, 1.0)
            self._rect = Rectangle(
                pos=self.pos,
                size=self.size,
            )


# Keep old name just in case any KV references it externally before being removed
class GradientBackground(SolidBackground):
    pass


class BaseScreen(Screen):
    """
    Base screen class that ALL pages inherit from.
    Automatically adds a solid background to every page.

    Usage:
        from components.base_screen import BaseScreen

        class HomeScreen(BaseScreen):
            pass
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        bg = SolidBackground()
        bg.pos = self.pos
        bg.size = self.size

        self.bind(pos=self._update_bg_pos, size=self._update_bg_size)

        # Add as the bottom-most child so content renders on top
        self.add_widget(bg, index=len(self.children))
        self._bg_widget = bg

    def _update_bg_pos(self, instance, value):
        if hasattr(self, '_bg_widget'):
            self._bg_widget.pos = value

    def _update_bg_size(self, instance, value):
        if hasattr(self, '_bg_widget'):
            self._bg_widget.size = value