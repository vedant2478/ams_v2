# components/base_screen.py
"""
Base screen with automatic gradient background.
All app screens should inherit from this class.

PERFORMANCE: Gradient texture is created ONCE at class level and reused
across all instances — avoids expensive 1024-pixel texture re-generation
on every pos/size change.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget
from kivy.graphics import Rectangle
from kivy.graphics.texture import Texture


class GradientBackground(Widget):
    """
    Reusable smooth gradient background widget.
    Creates a smooth blend from light blue (top) to dark blue (bottom).

    The texture is generated once and cached at the class level.
    Only the Rectangle position/size is updated on layout changes.
    """

    _cached_texture = None  # shared across all instances

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rect = None
        self.bind(pos=self._redraw, size=self._redraw)

    # ------------------------------------------------------------------
    # Texture creation (called once)
    # ------------------------------------------------------------------
    @classmethod
    def _build_texture(cls):
        texture = Texture.create(size=(1, 1024), colorfmt='rgb')
        gradient_data = []

        for i in range(1024):
            pos = i / 1023.0

            if pos < 0.30:
                t = pos / 0.30
                r = 0.20 - (0.20 - 0.08) * t
                g = 0.35 - (0.35 - 0.15) * t
                b = 0.50 - (0.50 - 0.25) * t
            elif pos < 0.55:
                t = (pos - 0.30) / 0.25
                r = 0.08 - (0.08 - 0.03) * t
                g = 0.15 - (0.15 - 0.08) * t
                b = 0.25 - (0.25 - 0.15) * t
            elif pos < 0.75:
                t = (pos - 0.55) / 0.20
                r = 0.03 - (0.03 - 0.01) * t
                g = 0.08 - (0.08 - 0.04) * t
                b = 0.15 - (0.15 - 0.08) * t
            else:
                r = 0.01
                g = 0.04
                b = 0.08

            gradient_data.extend([
                int(r * 255),
                int(g * 255),
                int(b * 255),
            ])

        buf = bytes(gradient_data)
        texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
        return texture

    # ------------------------------------------------------------------
    # Draw / redraw (cheap — just moves the Rectangle)
    # ------------------------------------------------------------------
    def _redraw(self, *args):
        if GradientBackground._cached_texture is None:
            GradientBackground._cached_texture = self._build_texture()

        self.canvas.before.clear()
        with self.canvas.before:
            self._rect = Rectangle(
                texture=GradientBackground._cached_texture,
                pos=self.pos,
                size=self.size,
            )


class BaseScreen(Screen):
    """
    Base screen class that ALL pages inherit from.
    Automatically adds a gradient background to every page.

    Usage:
        from components.base_screen import BaseScreen

        class HomeScreen(BaseScreen):
            pass
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        gradient = GradientBackground()
        gradient.pos = self.pos
        gradient.size = self.size

        self.bind(pos=self._update_gradient_pos, size=self._update_gradient_size)

        # Add as the bottom-most child so content renders on top
        self.add_widget(gradient, index=len(self.children))
        self._gradient_bg = gradient

    def _update_gradient_pos(self, instance, value):
        if hasattr(self, '_gradient_bg'):
            self._gradient_bg.pos = value

    def _update_gradient_size(self, instance, value):
        if hasattr(self, '_gradient_bg'):
            self._gradient_bg.size = value