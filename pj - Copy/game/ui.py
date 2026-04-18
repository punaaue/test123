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
        
        # Drop shadow
        self.ids.append(c.create_rectangle(x+4, y+4, x+w+4, y+h+4, fill="#000000", outline="", stipple="gray50"))
        # Main Button Body
        self.ids.append(c.create_rectangle(x, y, x+w, y+h, fill=col, outline=self._lighten(col), width=2))
        # Top inner highlight for 3D effect
        self.ids.append(c.create_rectangle(x+2, y+2, x+w-2, y+h//2, fill=self._lighten(self._lighten(col)), outline="", stipple="gray25"))
        
        # Text with subtle drop shadow
        self.ids.append(c.create_text(x+w//2+1, y+h//2+1, text=self.text, fill="#111111", font=("Segoe UI", self.font_size, "bold")))
        self.ids.append(c.create_text(x+w//2, y+h//2, text=self.text, fill=self.text_color, font=("Segoe UI", self.font_size, "bold")))

    def contains(self, mx, my):
        sf = getattr(self.canvas.app, "scale_f", 1.0) if hasattr(self.canvas, "app") else 1.0
        return self.x*sf <= mx <= (self.x + self.w)*sf and self.y*sf <= my <= (self.y + self.h)*sf

    def clear(self):
        for i in self.ids:
            self.canvas.delete(i)
        self.ids = []


def draw_bar(canvas, x, y, w, h, ratio, color=GREEN, bg=GRAY, **kwargs):
    """Draw an HP or progress bar with 3D style."""
    ratio = max(0, min(1, ratio))
    # Background
    canvas.create_rectangle(x, y, x+w, y+h, fill=bg, outline="", **kwargs)
    # Fill
    if ratio > 0:
        fw = int(w * ratio)
        canvas.create_rectangle(x, y, x + fw, y+h, fill=color, outline="", **kwargs)
        # Inner top highlight
        canvas.create_rectangle(x, y, x + fw, y + h//3, fill="#ffffff", outline="", stipple="gray25", **kwargs)
    # Border
    canvas.create_rectangle(x, y, x+w, y+h, fill="", outline="#111111", width=2, **kwargs)


def draw_card(canvas, x, y, w, h, char, selected=False):
    """Draw a character card with premium UI."""
    stars = char.get("stars", 1)
    
    # Rarity Borders
    if selected: outline, ow = GOLD, 3
    elif stars >= 13: outline, ow = RED, 4
    elif stars >= 10: outline, ow = GOLD, 3
    elif stars >= 8: outline, ow = PURPLE, 2
    elif stars >= 5: outline, ow = BLUE, 2
    else: outline, ow = "#444455", 1
    
    # Shadow and Body
    canvas.create_rectangle(x+4, y+4, x+w+4, y+h+4, fill="#000000", outline="", stipple="gray50")
    canvas.create_rectangle(x, y, x+w, y+h, fill=BG_CARD, outline=outline, width=ow)
    
    # Aura for 10+ stars
    if stars >= 13:
        canvas.create_rectangle(x+2, y+2, x+w-2, y+h-2, outline="#ff5722", width=1, stipple="gray25")
    elif stars >= 10:
        canvas.create_rectangle(x+2, y+2, x+w-2, y+h-2, outline="#ffeb3b", width=1, stipple="gray25")
        
    cx, cy = x + w//2, y + 25
    
    # Glow effect behind character icon
    glow_col = char.get("color", ACCENT)
    canvas.create_oval(cx-22, cy-22, cx+22, cy+22, fill=glow_col, outline="", stipple="gray25")
    canvas.create_oval(cx-16, cy-16, cx+16, cy+16, fill=glow_col, outline=WHITE, width=1)
    canvas.create_text(cx, cy, text=char.get("icon", "?"), font=("Segoe UI Emoji", 14))
    
    # Name
    canvas.create_text(x + w//2 + 1, y + 50, text=char["name"][:12], fill="#000000", font=("Segoe UI", 8, "bold"), width=w-4)
    canvas.create_text(x + w//2, y + 49, text=char["name"][:12], fill=WHITE, font=("Segoe UI", 8, "bold"), width=w-4)
    
    # Level + Rarity
    lvl = char.get("level", 1)
    canvas.create_text(x + w//2, y + 62, text=f"Lv.{lvl} ★x{stars}", fill=GOLD, font=("Segoe UI", 7))
    
    # Stats compact
    stats_y = y + 74
    for i, (label, key) in enumerate([("HP", "hp"), ("ATK", "atk"), ("DEF", "def")]):
        canvas.create_text(x + 5, stats_y + i*10, text=f"{label}:{char[key]}", fill="#aaaaaa", font=("Segoe UI", 7), anchor="w")
        
    # Crit Stats
    from game.constants import calc_char_crit
    cc, cd = calc_char_crit(char)
    canvas.create_text(x + w - 5, stats_y + 0*10, text=f"CR:{int(cc)}%", fill=ORANGE, font=("Segoe UI", 7), anchor="e")
    canvas.create_text(x + w - 5, stats_y + 1*10, text=f"CD:{int(cd)}%", fill=ORANGE, font=("Segoe UI", 7), anchor="e")
    canvas.create_text(x + w - 5, stats_y + 2*10, text=f"SPD:{char['spd']}", fill=CYAN, font=("Segoe UI", 7), anchor="e")

    # EXP bar
    if "exp" in char and lvl < MAX_LEVEL:
        needed = exp_for_level(lvl + 1)
        ratio = char["exp"] / needed if needed > 0 else 1
        draw_bar(canvas, x+5, y+h-10, w-10, 6, ratio, CYAN, "#222244")
