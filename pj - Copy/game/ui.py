# UI helper widgets for tkinter Canvas
from game.constants import *

class Button:
    """A styled button drawn on a tkinter Canvas."""
    def __init__(self, canvas, x, y, w, h, text, color=ACCENT, text_color=WHITE, font_size=16, command=None):
        self.canvas = canvas
        self.x, self.y, self.w, self.h = x, y, w, h
        self.text = text
        self.color = color
        self.hover_color = self._lighten(color)
        self.text_color = text_color
        self.font_size = font_size
        self.command = command
        self.is_hover = False
        self.ids = []

    def _lighten(self, hex_color):
        try:
            r = min(255, int(hex_color[1:3], 16) + 40)
            g = min(255, int(hex_color[3:5], 16) + 40)
            b = min(255, int(hex_color[5:7], 16) + 40)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return "#888888"

    def draw(self):
        c = self.canvas
        x, y, w, h = self.x, self.y, self.w, self.h
        col = self.hover_color if self.is_hover else self.color
        self.ids.append(c.create_rectangle(x+3, y+3, x+w+3, y+h+3, fill="#000000", outline="", stipple="gray25"))
        self.ids.append(c.create_rectangle(x, y, x+w, y+h, fill=col, outline=self._lighten(col), width=2))
        self.ids.append(c.create_text(x+w//2, y+h//2, text=self.text, fill=self.text_color,
                                       font=("Segoe UI", self.font_size, "bold")))

    def contains(self, mx, my):
        sf = getattr(self.canvas.app, "scale_f", 1.0) if hasattr(self.canvas, "app") else 1.0
        return self.x*sf <= mx <= (self.x + self.w)*sf and self.y*sf <= my <= (self.y + self.h)*sf

    def clear(self):
        for i in self.ids:
            self.canvas.delete(i)
        self.ids = []


def draw_bar(canvas, x, y, w, h, ratio, color=GREEN, bg=GRAY):
    """Draw an HP or progress bar."""
    ratio = max(0, min(1, ratio))
    canvas.create_rectangle(x, y, x+w, y+h, fill=bg, outline="")
    if ratio > 0:
        canvas.create_rectangle(x, y, x + int(w * ratio), y+h, fill=color, outline="")
    canvas.create_rectangle(x, y, x+w, y+h, fill="", outline="#333333", width=1)


def draw_card(canvas, x, y, w, h, char, selected=False):
    """Draw a character card with level info."""
    outline = GOLD if selected else "#333333"
    ow = 3 if selected else 1
    canvas.create_rectangle(x, y, x+w, y+h, fill=BG_CARD, outline=outline, width=ow)
    cx, cy = x + w//2, y + 30
    canvas.create_oval(cx-20, cy-20, cx+20, cy+20, fill=char.get("color", ACCENT), outline="")
    canvas.create_text(cx, cy, text=char.get("icon", "?"), font=("Segoe UI Emoji", 14))
    canvas.create_text(x + w//2, y + 58, text=char["name"], fill=WHITE, font=("Segoe UI", 8, "bold"), width=w-6)
    # Level + Rarity
    lvl = char.get("level", 1)
    canvas.create_text(x + w//2, y + 75, text=f"Lv.{lvl} {char.get('rarity', '★')}", fill=GOLD, font=("Segoe UI", 8))
    # Stats compact
    stats_y = y + 90
    for i, (label, key) in enumerate([("HP", "hp"), ("ATK", "atk"), ("DEF", "def")]):
        canvas.create_text(x + 8, stats_y + i*13, text=f"{label}:{char[key]}", fill="#aaaaaa",
                           font=("Segoe UI", 7), anchor="w")
    # EXP bar if has level
    if "exp" in char and lvl < MAX_LEVEL:
        needed = exp_for_level(lvl + 1)
        ratio = char["exp"] / needed if needed > 0 else 1
        draw_bar(canvas, x+5, y+h-14, w-10, 8, ratio, CYAN, "#222244")
