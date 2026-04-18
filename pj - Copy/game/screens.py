import random, copy, math, tkinter as tk
from game.constants import *
from game.ui import Button, draw_bar, draw_card
from game.battle import BattleMixin

class ScaledCanvas:
    def __init__(self, c, app):
        self.c = c
        self.app = app
    def _s(self, *coords):
        sf = getattr(self.app, 'scale_f', 1.0)
        return tuple(c * sf for c in coords)
    def _f(self, kw):
        sf = getattr(self.app, 'scale_f', 1.0)
        if "font" in kw:
            f = kw["font"]
            if isinstance(f, tuple) and len(f) >= 2:
                kw["font"] = (f[0], max(1, int(f[1]*sf))) + f[2:]
        if "width" in kw:
            kw["width"] = max(1, int(kw["width"]*sf))
    def create_rectangle(self, *coords, **kw): self._f(kw); return self.c.create_rectangle(*self._s(*coords), **kw)
    def create_text(self, x, y, **kw): self._f(kw); return self.c.create_text(*self._s(x,y), **kw)
    def create_oval(self, *coords, **kw): self._f(kw); return self.c.create_oval(*self._s(*coords), **kw)
    def create_line(self, *coords, **kw): self._f(kw); return self.c.create_line(*self._s(*coords), **kw)
    def coords(self, tag, *args): return self.c.coords(tag, *self._s(*args))
    def itemconfigure(self, tag, **kw): self._f(kw); return self.c.itemconfigure(tag, **kw)
    def delete(self, *args): self.c.delete(*args)
    def bind(self, *args): self.c.bind(*args)

class GameApp(BattleMixin):
    def __init__(self, root):
        import tkinter as tk
        self.root = root; self.root.title("Gacha Quest"); self.root.resizable(False, False)
        self.root.configure(bg="#000")
        self.raw_canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg=BG_DARK, highlightthickness=0)
        self.raw_canvas.pack(expand=True)
        self.scale_f = 1.0
        self.canvas = ScaledCanvas(self.raw_canvas, self)
        self.buttons = []; self.owned_chars = []; self.party = []
        self.gold = 500; self.backpack = {"exp_potion_1": 3}; self.shards = {}
        self.runes_inventory = []; self.equipped_runes = [None, None, None]
        self.gear_inventory = []; self.max_dungeon_cleared = 0
        self.active_buffs = {}; self.state = "menu"; self.anim_frame = 0
        self.stage_page = 0; self.bp_selected_char = None; self.max_stage_cleared = 0
        self.notif_msg = ""; self.notif_timer = 0
        import time
        self.afk_stage = 0; self.last_afk_time = time.time(); self.afk_log = []; self.afk_reward_count = 0
        self.bp_item_page = 0
        self.armory_multi_mode = False; self.armory_selected_ids = set()
        self.current_save_file = SAVE_FILE
        self.target_fps = load_settings().get("target_fps", 30)
        self.canvas.bind("<Button-1>", self.on_click); self.canvas.bind("<Motion>", self.on_motion)
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.toggle_fullscreen() if getattr(self, "is_fullscreen", False) else None)
        self.draw_menu(); self.animate()

    def _try_load(self, filename):
        data = load_game(filename)
        if data:
            self.gold = data.get("gold", 500)
            self.backpack = data.get("backpack", {"exp_potion_1": 3})
            self.max_stage_cleared = data.get("max_stage_cleared", 0)
            self.owned_chars = data.get("owned_chars", [])
            self.shards = data.get("shards", {})
            self.runes_inventory = data.get("runes_inventory", [])
            self.equipped_runes = data.get("equipped_runes", [None, None, None])
            self.gear_inventory = data.get("gear_inventory", [])
            self.max_dungeon_cleared = data.get("max_dungeon_cleared", 0)
            
            # Migration: Update old characters with new skill names, target types, and gear slots
            from game.constants import ALL_CHARACTERS, GEAR_SLOTS
            for ch in self.owned_chars:
                tpl = next((t for t in ALL_CHARACTERS if t["name"] == ch["name"]), None)
                if tpl:
                    ch["skill"] = tpl.get("skill", "Attack")
                    ch["target_type"] = tpl.get("target_type", "single")
                if "gear" not in ch:
                    ch["gear"] = {s: None for s in GEAR_SLOTS}
            
            party_indices = data.get("party_indices", [])
            self.party = [self.owned_chars[i] for i in party_indices if i < len(self.owned_chars)]
            return True
        return False

    def _add_starting_chars(self):
        from game.constants import ALL_CHARACTERS, make_new_char
        starters = ["Slime", "Apprentice", "Blaze Knight"]
        for name in starters:
            tpl = next((c for c in ALL_CHARACTERS if c["name"] == name), ALL_CHARACTERS[0])
            new_ch = make_new_char(tpl)
            self.owned_chars.append(new_ch)
            if len(self.party) < 3: self.party.append(new_ch)
        self.do_save()

    def do_save(self):
        party_idx = [self.owned_chars.index(c) for c in self.party if c in self.owned_chars]
        save_game({"gold": self.gold, "backpack": self.backpack, "max_stage_cleared": self.max_stage_cleared,
                   "owned_chars": self.owned_chars, "party_indices": party_idx, "shards": getattr(self, "shards", {}),
                   "runes_inventory": getattr(self, "runes_inventory", []), "equipped_runes": getattr(self, "equipped_runes", [None, None, None]),
                   "gear_inventory": getattr(self, "gear_inventory", []), "max_dungeon_cleared": getattr(self, "max_dungeon_cleared", 0)}, self.current_save_file)

    def do_reset(self):
        delete_save(self.current_save_file); self.owned_chars=[]; self.party=[]; self.gold=500
        self.backpack={"exp_potion_1":3}; self.max_stage_cleared=0; self.active_buffs={}; self.shards={}
        self.runes_inventory=[]; self.equipped_runes=[None, None, None]
        self.gear_inventory=[]; self.max_dungeon_cleared=0
        self._add_starting_chars()
        self.goto_hub()

    def animate(self):
        self.anim_frame += 1
        if self.state == "menu": self._update_menu_ui()
        elif self.state in ("gacha", "rune_gacha"):
            if hasattr(self, "_update_gacha_ui"): self._update_gacha_ui()
        elif self.state == "battle":
            if hasattr(self, "_update_particles"): self._update_particles()
            if getattr(self, "b_shake", 0) > 0:
                fps_scale = 30 / getattr(self, "target_fps", 30)
                self.b_shake = max(0, self.b_shake - (2 * fps_scale))
            if getattr(self, "b_flash", None): self.b_flash = None
            self.draw_battle()
        elif self.state == "afk":
            import time
            now = time.time()
            if now - self.last_afk_time >= 1.0:
                self.last_afk_time = now
                self._do_afk_reward()
                # Log is updated inside _do_afk_reward
            
            # Save every 30 seconds in AFK
            if self.anim_frame % 600 == 0: self.do_save()
            
            self._update_afk_ui()
            
        # Notification Logic (Global)
        self.canvas.delete("notif")
        if self.notif_timer > 0:
            self.notif_timer -= 1
            self.canvas.create_text(WIDTH//2, HEIGHT-30, text=self.notif_msg, fill=GREEN, font=("Segoe UI", 10, "bold"), tags="notif")
        delay = int(1000 / getattr(self, "target_fps", 30))
        self.root.after(delay, self.animate)

    def goto_afk(self):
        import time
        self.state="afk"; self.afk_log=[]; self.last_afk_time = time.time()
        self.afk_click_count = 0; self.draw_afk()
    def draw_afk(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0a101a",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#16213e",outline="#30363d")
        c.create_text(20,30,text="🏠 Idle Training Area (AFK)",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        
        stg = get_stage(self.afk_stage)
        c.create_text(WIDTH//2, 100, text=f"Currently Training in: {stg['name']}", fill=GOLD, font=("Segoe UI", 14, "bold"))
        
        # Progress bar (Static parts)
        bx, by, bw, bh = WIDTH//2-150, 130, 300, 15
        c.create_rectangle(bx, by, bx+bw, by+bh, fill="#222", outline="", tags="afk_static")
        c.create_rectangle(bx, by, bx, by+bh, fill=GREEN, outline="", tags="afk_bar_fill")
        c.create_rectangle(bx, by, bx+bw, by+bh, fill="", outline="#333", width=1, tags="afk_static")
        c.create_text(WIDTH//2, 160, text="", fill="#888", font=("Segoe UI", 10), tags="afk_timer_txt")

        # Log (Static container)
        c.create_text(WIDTH//2, 200, text="Recent Loot Log:", fill=WHITE, font=("Segoe UI", 12, "bold"))
        c.create_rectangle(100, 220, WIDTH-100, 480, fill="#161b22", outline="#333")
        
        # Recent Log Text (Placeholders for 10 lines)
        for i in range(10):
            c.create_text(WIDTH//2, 240 + i*22, text="", fill="#aaa", font=("Segoe UI", 9), tags=f"afk_log_{i}")
        self._update_afk_log_ui()
            
        # Controls
        c_clicks = getattr(self, "afk_click_count", 0)
        self.add_btn(WIDTH//2-200, 520, 180, 40, "Change Stage", "#4a148c", command=self._afk_change_stage)
        self.add_btn(WIDTH//2+20, 520, 180, 40, "Stop & Leave", "#b71c1c", command=self._stop_afk)
        
        # Clicker Button
        self.add_btn(WIDTH//2-100, 175, 200, 35, f"👆 CLICK! ({c_clicks}/2)", "#ff9100", font_size=12, command=self._afk_click)
        
        self._update_afk_ui()

    def _afk_click(self):
        self.afk_click_count = getattr(self, "afk_click_count", 0) + 1
        if self.afk_click_count >= 2:
            self.afk_click_count = 0
            self._do_afk_reward()
            self.notif_msg = "Bonus Click Reward!"; self.notif_timer = 20
        self.draw_afk()

    def _stop_afk(self):
        self.do_save() # Final save when leaving
        self.goto_stages()

    def _update_afk_log_ui(self):
        c=self.canvas
        logs = self.afk_log[-10:]
        for i in range(10):
            msg = logs[i] if i < len(logs) else ""
            c.itemconfigure(f"afk_log_{i}", text=msg)

    def _update_afk_ui(self):
        c=self.canvas; import time
        elapsed = time.time() - self.last_afk_time
        ratio = min(1.0, elapsed/1.0)
        
        # Update bar size and text using scaled coordinates
        bx, by, bw, bh = WIDTH//2-150, 130, 300, 15
        c.coords("afk_bar_fill", bx, by, bx + int(bw * ratio), by+bh)
        c.itemconfigure("afk_timer_txt", text=f"Next Reward in: {max(0, 1.0 - elapsed):.1f}s")

    def _afk_change_stage(self):
        self.state = "afk_select"; self.afk_sel_page = 0; self.draw_afk_select()

    def draw_afk_select(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0a101a",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#16213e",outline="#30363d")
        c.create_text(20,30,text="🎯 Select AFK Training Stage",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        
        per_page = 30; start = getattr(self, "afk_sel_page", 0) * per_page
        for i in range(per_page):
            idx = start + i
            if idx > self.max_stage_cleared: break
            
            row, col = i//5, i%5
            x = 60 + col * 160; y = 90 + row * 60
            stg = get_stage(idx)
            btn_color = "#1a237e" if idx == self.afk_stage else "#333"
            self.add_btn(x, y, 140, 45, f"Stage {idx+1}", btn_color, font_size=10, command=lambda idx=idx: self._confirm_afk_stage(idx))

        # Paging
        if getattr(self, "afk_sel_page", 0) > 0:
            self.add_btn(WIDTH//2-180, HEIGHT-50, 100, 35, "← Prev", "#444", command=lambda: self._afk_sel_p(-1))
        if start + per_page <= self.max_stage_cleared:
            self.add_btn(WIDTH//2+80, HEIGHT-50, 100, 35, "Next →", "#444", command=lambda: self._afk_sel_p(1))
            
        self.add_btn(WIDTH//2-50, HEIGHT-50, 100, 35, "Cancel", GRAY, command=self.goto_afk)

    def _afk_sel_p(self, d): self.afk_sel_page += d; self.draw_afk_select()
    def _confirm_afk_stage(self, idx):
        self.afk_stage = idx
        self.afk_log = [f"Started training at: {get_stage(idx)['name']}"]
        self.goto_afk()

    def _do_afk_reward(self):
        idx = self.afk_stage
        # Boosted: Gold x5, EXP x2, Loot 10%
        gold = ((get_stage_gold_reward(idx) // 50) + 1) * 5
        self.gold += gold
        msg = f"+{gold}g"
        
        # EXP for party (Boosted x2)
        for ch in self.party:
            exp = 4 * (idx + 1)
            add_exp(ch, exp)
            
        # Random Loot (Boosted to 10% chance)
        if random.random() < 0.10:
            loot = roll_loot(idx, include_ticket=False)
            if loot:
                it = ITEMS[loot[0]]
                self.backpack[loot[0]] = self.backpack.get(loot[0], 0) + 1
                msg += f" | Found: {it['icon']} {it['name']}"
        
        # Skip Ticket Chance (5% to get 1-5)
        if random.random() < 0.05:
            qty = random.randint(1, 5)
            self.backpack["skip_ticket"] = self.backpack.get("skip_ticket", 0) + qty
            msg += f" | +{qty} 🎟️ Ticket"
        
        self.afk_reward_count += 1
        self.afk_log.append(f"[{self.afk_reward_count}] {msg}")
        if len(self.afk_log) > 50: self.afk_log.pop(0) # Keep a bit more history
        self._update_afk_log_ui()
        # Removed auto-save every second to prevent disk lag

    def clear(self): self.canvas.delete("all"); self.buttons = []
    def add_btn(self, *a, **kw):
        b = Button(self.canvas, *a, **kw)
        if hasattr(self, 'mx'): b.is_hover = b.contains(self.mx, self.my)
        b.draw(); self.buttons.append(b); return b
    def on_click(self, e):
        for b in self.buttons:
            if b.contains(e.x, e.y) and b.command: b.command(); return
    def on_motion(self, e):
        self.mx, self.my = e.x, e.y
        ch = False
        for b in self.buttons:
            was = b.is_hover; b.is_hover = b.contains(e.x, e.y)
            if was != b.is_hover: ch = True
        if ch and self.state not in ("menu",):
            getattr(self, f"draw_{self.state}", lambda: None)()
            
    def get_max_party_size(self):
        return 4 if self.max_stage_cleared >= 50 else 3

    def toggle_fullscreen(self):
        self.is_fullscreen = not getattr(self, "is_fullscreen", False)
        self.root.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            w = self.root.winfo_screenwidth()
            h = self.root.winfo_screenheight()
            self.scale_f = min(w/WIDTH, h/HEIGHT)
        else:
            self.scale_f = 1.0
            
        self.raw_canvas.config(width=int(WIDTH*self.scale_f), height=int(HEIGHT*self.scale_f))
            
        if getattr(self, "state", None) != "menu":
            getattr(self, f"draw_{self.state}", lambda: None)()
        else:
            self.draw_menu()

    # ── MENU ──
    def draw_menu(self):
        self.clear(); c=self.canvas; self.buttons=[]
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#000",outline="")
        self.add_btn(WIDTH//2-100,300,200,55,"▶  START",ACCENT,command=self.goto_save_slots)
        self.add_btn(WIDTH//2-100,375,200,55,"⚙️  SETTINGS",BLUE,command=self.goto_settings)
        self.add_btn(WIDTH//2-100,450,200,55,"✕  QUIT",GRAY,command=self.root.destroy)
        self._update_menu_ui()
        
    def goto_settings(self):
        self.state = "settings"
        self.draw_settings()
        
    def _set_fps(self, fps):
        self.target_fps = fps
        save_settings({"target_fps": fps})
        self.draw_settings()

    def draw_settings(self):
        self.clear(); c=self.canvas; self.buttons=[]
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#050510",outline="")
        c.create_text(WIDTH//2, 100, text="⚙️ SETTINGS", fill=WHITE, font=("Segoe UI", 28, "bold"))
        
        c.create_text(WIDTH//2, 180, text="Target Framerate (FPS)", fill=GOLD, font=("Segoe UI", 16, "bold"))
        c.create_text(WIDTH//2, 210, text="Higher FPS means smoother animations but uses more CPU.", fill="#888", font=("Segoe UI", 12))
        
        # FPS Toggles
        fps = getattr(self, "target_fps", 30)
        c20 = GREEN if fps == 20 else GRAY
        c30 = GREEN if fps == 30 else GRAY
        c60 = GREEN if fps == 60 else GRAY
        
        self.add_btn(WIDTH//2-160, 260, 100, 50, "20 FPS", c20, command=lambda: self._set_fps(20))
        self.add_btn(WIDTH//2-50,  260, 100, 50, "30 FPS", c30, command=lambda: self._set_fps(30))
        self.add_btn(WIDTH//2+60,  260, 100, 50, "60 FPS", c60, command=lambda: self._set_fps(60))
        
        self.add_btn(WIDTH//2-100, 480, 200, 50, "BACK", GRAY, command=self.back_menu)
        
    def goto_save_slots(self):
        self.state = "saves"
        # Auto-migrate old save
        import os, shutil
        if os.path.exists(SAVE_FILE) and not os.path.exists("savegame_slot_1.json"):
            try: shutil.copy(SAVE_FILE, "savegame_slot_1.json")
            except: pass
        self.draw_save_slots()
        
    def _select_slot(self, slot_num):
        self.current_save_file = f"savegame_slot_{slot_num}.json"
        # Reset internal state
        self.owned_chars=[]; self.party=[]; self.gold=500
        self.backpack={"exp_potion_1":3}; self.max_stage_cleared=0; self.active_buffs={}; self.shards={}
        self.runes_inventory=[]; self.equipped_runes=[None, None, None]
        self.gear_inventory=[]; self.max_dungeon_cleared=0
        
        if self._try_load(self.current_save_file):
            self.goto_hub()
        else:
            self._add_starting_chars()
            self.goto_hub()
            
    def _delete_slot(self, slot_num):
        delete_save(f"savegame_slot_{slot_num}.json")
        self.draw_save_slots()

    def draw_save_slots(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#050510",outline="")
        c.create_text(WIDTH//2, 80, text="SELECT SAVE SLOT", fill=WHITE, font=("Segoe UI", 24, "bold"))
        
        for i in range(1, 4):
            y = 150 + (i-1) * 110
            fname = f"savegame_slot_{i}.json"
            prev = preview_save(fname)
            
            # Panel
            c.create_rectangle(WIDTH//2-250, y, WIDTH//2+250, y+90, fill="#161b22", outline="#30363d", width=2)
            c.create_text(WIDTH//2-230, y+25, text=f"Slot {i}", fill=ACCENT, font=("Segoe UI", 16, "bold"), anchor="w")
            
            if prev:
                c.create_text(WIDTH//2-230, y+55, text=f"Stage: {prev['max_stage']}  |  Gold: {prev['gold']}  |  Heroes: {prev['chars_count']}", fill="#aaa", font=("Segoe UI", 12), anchor="w")
                self.add_btn(WIDTH//2+130, y+25, 100, 40, "LOAD", GREEN, command=lambda n=i: self._select_slot(n))
                self.add_btn(WIDTH//2+50, y+35, 70, 30, "Delete", RED, font_size=9, command=lambda n=i: self._delete_slot(n))
            else:
                c.create_text(WIDTH//2-230, y+55, text="[ EMPTY SLOT ]", fill="#555", font=("Segoe UI", 12), anchor="w")
                self.add_btn(WIDTH//2+130, y+25, 100, 40, "NEW GAME", BLUE, command=lambda n=i: self._select_slot(n))
                
        self.add_btn(WIDTH//2-100, 500, 200, 40, "BACK TO TITLE", GRAY, command=self.back_menu)

    def _update_menu_ui(self):
        c=self.canvas; c.delete("menu_dyn"); f=self.anim_frame
        for i in range(20):
            px=(i*47+f*(1+i%3))%WIDTH; py=(i*31+f*(2+i%2))%HEIGHT
            c.create_oval(px-2,py-2,px+2,py+2,fill=ACCENT,outline="",tags="menu_dyn")
        off=math.sin(f*0.1)*5
        c.create_text(WIDTH//2,170+off,text="⚔️ GACHA QUEST ⚔️",fill=GOLD,font=("Segoe UI",42,"bold"),tags="menu_dyn")
        c.create_text(WIDTH//2,230,text="Turn-Based RPG",fill="#888",font=("Segoe UI",14),tags="menu_dyn")

    # ── HUB ──
    def goto_hub(self): self.state="hub"; self.draw_hub()
    def back_menu(self): self.state="menu"; self.anim_frame=0; self.draw_menu()

    def draw_hub(self):
        self.clear(); c=self.canvas
        # Premium Background with Animated-like Gradient Grid
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0b0b1a",outline="")
        
        # Animated particles
        f = getattr(self, "anim_frame", 0)
        for i in range(25):
            px = (i * 73 + f * 0.8) % WIDTH
            py = (i * 51 - f * 0.5) % HEIGHT
            sz = (i % 3) + 1
            c.create_oval(px, py, px+sz, py+sz, fill=CYAN if i%2==0 else PURPLE, outline="")

        for i in range(15): 
            c.create_line(0, i*45, WIDTH, i*45, fill="#1c1c3d", width=1, dash=(4,4))
            c.create_line(i*65, 0, i*65, HEIGHT, fill="#1c1c3d", width=1, dash=(4,4))
            
        # Top Header Bar with shadow
        c.create_rectangle(0,0,WIDTH,65,fill="#000000",outline="", stipple="gray50") # shadow
        c.create_rectangle(0,0,WIDTH,60,fill="#161b22",outline="#30363d")
        c.create_text(70,30,text="⚔️ Gacha Quest",fill=WHITE,font=("Segoe UI",18,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"💰 {self.gold}  🎟️ {self.backpack.get('skip_ticket', 0)}",fill=GOLD,font=("Segoe UI",14),anchor="e")
        
        # Dashboard Panel Shadow
        c.create_rectangle(WIDTH//2-221, 99, WIDTH//2+229, HEIGHT-25, fill="#000000", outline="", stipple="gray50")
        c.create_rectangle(WIDTH//2-225, 95, WIDTH//2+225, HEIGHT-30, fill="#161b22", outline="#444455", width=2)
        
        # Glow around title
        c.create_text(WIDTH//2, 120, text="COMMAND CENTER", fill=ACCENT, font=("Segoe UI", 20, "bold"))
        c.create_text(WIDTH//2, 145, text=f"Stage: {self.max_stage_cleared} • Dungeon: {getattr(self,'max_dungeon_cleared',0)} • Party: {len(self.party)}", fill="#aaaaaa", font=("Segoe UI", 10))

        # Grid Buttons (2 Columns, 5 Rows)
        bx1 = WIDTH//2 - 200; bx2 = WIDTH//2 + 5; bw = 195; bh = 50
        # Row 1
        self.add_btn(bx1, 170, bw, bh, "⚔️ STAGES", "#1a237e", font_size=12, command=self.goto_stages)
        self.add_btn(bx2, 170, bw, bh, "🎰 GACHA", "#4a148c", font_size=12, command=self.goto_gacha_select)
        # Row 2
        self.add_btn(bx1, 230, bw, bh, "👥 PARTY", "#1b5e20", font_size=12, command=self.goto_party)
        self.add_btn(bx2, 230, bw, bh, "🎒 BACKPACK", "#e65100", font_size=12, command=self.goto_backpack)
        # Row 3
        self.add_btn(bx1, 290, bw, bh, "🗡️ ARMORY", "#6a1b9a", font_size=12, command=self.goto_armory)
        self.add_btn(bx2, 290, bw, bh, "📖 INDEX", "#006064", font_size=12, command=self.goto_index)
        # Row 4
        self.add_btn(bx1, 350, bw, bh, "🆙 ASCEND", "#f57f17", font_size=12, command=self.goto_ascension)
        self.add_btn(bx2, 350, bw, bh, "💠 RUNE BOARD", "#880e4f", font_size=12, command=self.goto_rune_board)
        # Row 5
        self.add_btn(bx1, 410, bw, bh, "🏆 ACHIEVEMENTS", "#b71c1c", font_size=12, command=self.goto_achievements)
        self.add_btn(bx2, 410, bw, bh, "💾 SAVE GAME", "#1565c0", font_size=12, command=self._save_notify)

        # Footer
        self.add_btn(bx1, 475, 400, 28, "↩ BACK TO TITLE", "#444", font_size=9, command=self.back_menu)
        
        # discreet Reset at bottom-right
        self.add_btn(WIDTH-100, HEIGHT-35, 80, 22, "Reset Slot", "#331111", font_size=8, command=self.do_reset)

    def _save_notify(self):
        self.do_save()
        self.notif_msg = "💾 Progress Saved Successfully!"; self.notif_timer = 60 # 3 seconds at 20fps

    # ── INDEX (COLLECTION) ──
    def goto_index(self): self.state="index"; self.index_page=0; self.draw_index()
    def draw_index(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#050510",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#161b22",outline="#30363d")
        c.create_text(20,30,text="📖 Character Index",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        
        owned_names = {ch["name"] for ch in self.owned_chars}
        from game.constants import ALL_CHARACTERS
        
        # Pagination
        per_page = 20; start = self.index_page * per_page
        subset = ALL_CHARACTERS[start : start + per_page]
        
        c.create_text(WIDTH-20,30,text=f"Collected: {len(owned_names)}/{len(ALL_CHARACTERS)}",fill=GOLD,font=("Segoe UI",12),anchor="e")
        
        cw, ch_h = 130, 160
        for i, itm in enumerate(subset):
            row, col = i//5, i%5
            x = 80 + col * (cw + 30); y = 80 + row * (ch_h + 30)
            is_owned = itm["name"] in owned_names
            
            if is_owned:
                draw_card(c, x, y, cw, ch_h, itm)
            else:
                # Silhouette for unowned
                c.create_rectangle(x, y, x+cw, y+ch_h, fill="#111", outline="#333", width=2)
                c.create_text(x+cw//2, y+ch_h//2, text="?", fill="#444", font=("Segoe UI", 30, "bold"))
                c.create_text(x+cw//2, y+ch_h-20, text=f"{itm['stars']}★", fill="#333", font=("Segoe UI", 10))

        # Paging Buttons
        if self.index_page > 0:
            self.add_btn(40, HEIGHT-50, 120, 35, "← Previous", "#333", command=lambda: self._page_index(-1))
        if start + per_page < len(ALL_CHARACTERS):
            self.add_btn(WIDTH-160, HEIGHT-50, 120, 35, "Next →", "#333", command=lambda: self._page_index(1))
            
        self.add_btn(WIDTH//2-60, HEIGHT-50, 120, 35, "Back", GRAY, command=self.goto_hub)

    def _page_index(self, d): self.index_page += d; self.draw_index()

    # ── GACHA SELECT ──
    def goto_gacha_select(self):
        self.state="gacha_select"; self.draw_gacha_select()
        
    def draw_gacha_select(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0b0514",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#1a1a2e",outline="#30363d")
        c.create_text(20,30,text="🎰 Select Summon Type",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        
        # Hero Summon Banner
        c.create_rectangle(100, 150, 430, 450, fill="#161b22", outline=PURPLE, width=2)
        c.create_text(265, 200, text="🦸 HERO SUMMON", fill=PURPLE, font=("Segoe UI", 20, "bold"))
        c.create_text(265, 250, text="Summon powerful characters\nNormal, High, and Super Tiers.", fill="#aaa", font=("Segoe UI", 12), justify="center")
        self.add_btn(165, 350, 200, 50, "ENTER", PURPLE, font_size=14, command=self.goto_hero_gacha)
        
        # Rune Summon Banner
        c.create_rectangle(470, 150, 800, 450, fill="#161b22", outline=GOLD, width=2)
        c.create_text(635, 200, text="💠 RUNE SUMMON", fill=GOLD, font=("Segoe UI", 20, "bold"))
        c.create_text(635, 250, text="Summon Global Stat Runes\nEquip in Rune Board for buffs.", fill="#aaa", font=("Segoe UI", 12), justify="center")
        if self.max_stage_cleared >= 40:
            self.add_btn(535, 350, 200, 50, "ENTER", GOLD, font_size=14, command=self.goto_rune_gacha)
        else:
            c.create_text(635, 375, text="🔒 Unlocks at Stage 40", fill=RED, font=("Segoe UI", 12, "bold"))
            
        self.add_btn(WIDTH//2-100, 520, 200, 40, "← Hub", GRAY, font_size=12, command=self.goto_hub)

    # ── HERO GACHA ──
    def goto_hero_gacha(self): 
        self.state="gacha"; self.gacha_results=[]; self.gacha_mode="normal"
        self.gacha_stars = [(random.randint(0,WIDTH), random.randint(0,HEIGHT), random.randint(1,3), random.choice([PURPLE, GOLD, WHITE, CYAN])) for _ in range(40)]
        self.draw_hero_gacha()

    def _update_gacha_ui(self):
        c=self.canvas; c.delete("gacha_stars"); f=self.anim_frame
        for sx, sy, sz, scol in self.gacha_stars:
            glow = math.sin(f*0.1 + sx) * 0.5 + 0.5
            c.create_oval(sx, sy, sx+sz+glow*2, sy+sz+glow*2, fill=scol, outline="", tags="gacha_stars")

    def draw_hero_gacha(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0b0514",outline="")
        self._update_gacha_ui()
            
        c.create_rectangle(0,0,WIDTH,65,fill="#000000",outline="", stipple="gray50")
        c.create_rectangle(0,0,WIDTH,60,fill="#1a1a2e",outline="#30363d")
        c.create_text(20,30,text="🦸 Hero Gacha",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"💰 {self.gold} Gold",fill=GOLD,font=("Segoe UI",14),anchor="e")
        
        nc="#5c2d91" if self.gacha_mode=="normal" else "#333"
        hc="#b71c1c" if self.gacha_mode=="high" else "#333"
        sc="#ffd740" if self.gacha_mode=="super" else "#333"
        hy_c="#ff1744" if self.gacha_mode=="hyper" else "#333"
        
        self.add_btn(10,70,210,35,"Normal (1-6★)",nc,font_size=10,command=lambda:self._set_hero_gacha("normal"))
        
        if self.max_stage_cleared >= 20: self.add_btn(230,70,210,35,f"High (4-10★)",hc,font_size=10,command=lambda:self._set_hero_gacha("high"))
        else: c.create_text(335, 87, text="🔒 High (Stage 20)", fill="#555", font=("Segoe UI", 10))
        
        if self.max_stage_cleared >= 50: self.add_btn(450,70,210,35,f"SUPER (7-12★)",sc,font_size=10,command=lambda:self._set_hero_gacha("super"))
        else: c.create_text(555, 87, text="🔒 Super (Stage 50)", fill="#555", font=("Segoe UI", 10))
        
        if self.max_stage_cleared >= 80: self.add_btn(670,70,210,35,f"HYPER (10-15★)",hy_c,font_size=10,command=lambda:self._set_hero_gacha("hyper"))
        else: c.create_text(775, 87, text="🔒 Hyper (Stage 80)", fill="#555", font=("Segoe UI", 10))
        
        mode = self.gacha_mode
        if mode == "hyper": rates, cost = HYPER_RATES, HYPER_COST
        elif mode == "super": rates, cost = SUPER_RATES, SUPER_COST
        elif mode == "high": rates, cost = HIGH_RATES, HIGH_COST
        else: rates, cost = NORMAL_RATES, NORMAL_COST
        rate_str = "  ".join(f"{s}★:{r}%" for s,r in rates.items())
        c.create_text(WIDTH//2,125,text=f"Cost: {cost:,}g | Rates: {rate_str}",fill="#aaa",font=("Segoe UI",8))
        
        if self.gacha_results:
            cw=110; ch_h=130
            cols=min(5,len(self.gacha_results)); sx=(WIDTH-cols*(cw+8))//2
            for i,ch in enumerate(self.gacha_results):
                col=i%5; row=i//5; x=sx+col*(cw+8); y=145+row*(ch_h+8)
                draw_card(c,x,y,cw,ch_h,ch)
                stars = ch.get("stars", 1)
                txt = f"★x{stars}" + (" (Dup)" if ch.get("is_duplicate") else "")
                c.create_text(x+cw//2,y+ch_h+8,text=txt,fill=RED if ch.get("is_duplicate") else GOLD,font=("Segoe UI", 7, "bold"))
        else:
            c.create_text(WIDTH//2,250,text="🎰",font=("Segoe UI Emoji",45))
            c.create_text(WIDTH//2,320,text="Summon Heroes!",fill=WHITE,font=("Segoe UI",20,"bold"))
            
        by=440 if not self.gacha_results or len(self.gacha_results)<=5 else 430
        self.add_btn(60,by,180,45,f"🎲 x1 ({cost}g)",PURPLE,font_size=12,command=lambda:self._do_hero_gacha(1))
        self.add_btn(260,by,210,45,f"🎲 x10 ({cost*10}g)",PURPLE,font_size=12,command=lambda:self._do_hero_gacha(10))
        self.add_btn(490,by,160,45,"← Back",GRAY,font_size=12,command=self.goto_gacha_select)

    def _set_hero_gacha(self, mode): self.gacha_mode=mode; self.gacha_results=[]; self.draw_hero_gacha()

    def _do_hero_gacha(self, count):
        mode = self.gacha_mode
        if mode == "hyper": cost, roll_fn = HYPER_COST * count, roll_hyper
        elif mode == "super": cost, roll_fn = SUPER_COST * count, roll_super
        elif mode == "high": cost, roll_fn = HIGH_COST * count, roll_high
        else: cost, roll_fn = NORMAL_COST * count, roll_normal
        if self.gold < cost:
            self.gacha_results=[]; self.draw_hero_gacha()
            self.canvas.create_text(WIDTH//2,400,text="Not enough gold!",fill=RED,font=("Segoe UI",14,"bold")); return
        self.gold -= cost; self.gacha_results=[]
        for _ in range(count):
            ch = roll_fn()
            if any(existing["name"] == ch["name"] for existing in self.owned_chars):
                ch["is_duplicate"] = True
                self.shards[ch["name"]] = self.shards.get(ch["name"], 0) + 1
            else:
                self.owned_chars.append(ch)
            self.gacha_results.append(ch)
        self.do_save(); self.draw_hero_gacha()

    # ── RUNE GACHA ──
    def goto_rune_gacha(self):
        self.state = "rune_gacha"; self.rune_results = []
        self.gacha_stars = [(random.randint(0,WIDTH), random.randint(0,HEIGHT), random.randint(1,3), random.choice([PURPLE, GOLD, WHITE, CYAN])) for _ in range(40)]
        self.draw_rune_gacha()
        
    def draw_rune_gacha(self):
        self.clear(); c = self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0b0514",outline="")
        self._update_gacha_ui()
        c.create_rectangle(0,0,WIDTH,65,fill="#000000",outline="", stipple="gray50")
        c.create_rectangle(0,0,WIDTH,60,fill="#1a1a2e",outline="#30363d")
        c.create_text(20,30,text="💠 Rune Summon",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"💰 {self.gold} Gold",fill=GOLD,font=("Segoe UI",14),anchor="e")
        
        c.create_text(WIDTH//2, 100, text="Summon Global Stat Runes", fill=GOLD, font=("Segoe UI", 16, "bold"))
        from game.constants import RUNE_COST, RUNE_TIERS
        rates_str = "  |  ".join(f"{t}: {int(d['chance']*100)}%" for t, d in RUNE_TIERS.items())
        c.create_text(WIDTH//2, 130, text=f"Cost: {RUNE_COST}g  |  Rates:  {rates_str}", fill="#aaa", font=("Segoe UI", 10))
        
        if getattr(self, "rune_results", []):
            cw=160; ch_h=180
            cols=min(5,len(self.rune_results)); sx=(WIDTH-cols*(cw+10))//2
            for i, rune in enumerate(self.rune_results):
                col=i%5; row=i//5; x=sx+col*(cw+10); y=180+row*(ch_h+10)
                c.create_rectangle(x, y, x+cw, y+ch_h, fill="#161b22", outline=rune["color"], width=2)
                c.create_text(x+cw//2, y+40, text=rune["icon"], font=("Segoe UI Emoji", 40))
                c.create_text(x+cw//2, y+90, text=rune["tier"], fill=rune["color"], font=("Segoe UI", 12, "bold"))
                c.create_text(x+cw//2, y+120, text=rune["name"], fill=WHITE, font=("Segoe UI", 10))
                c.create_text(x+cw//2, y+150, text=rune["desc"], fill=GREEN, font=("Segoe UI", 9))
        else:
            c.create_text(WIDTH//2,250,text="💠",font=("Segoe UI Emoji",45))
            c.create_text(WIDTH//2,320,text="Summon Runes!",fill=WHITE,font=("Segoe UI",20,"bold"))
            
        by=440
        self.add_btn(160,by,180,45,f"🎲 x1 ({RUNE_COST}g)",GOLD,font_size=12,command=lambda:self._do_rune_gacha(1))
        self.add_btn(360,by,210,45,f"🎲 x10 ({RUNE_COST*10}g)",GOLD,font_size=12,command=lambda:self._do_rune_gacha(10))
        self.add_btn(600,by,160,45,"← Back",GRAY,font_size=12,command=self.goto_gacha_select)

    def _do_rune_gacha(self, count):
        from game.constants import RUNE_COST, roll_rune
        cost = RUNE_COST * count
        if self.gold < cost:
            self.rune_results=[]; self.draw_rune_gacha()
            self.canvas.create_text(WIDTH//2,400,text="Not enough gold!",fill=RED,font=("Segoe UI",14,"bold")); return
        self.gold -= cost; self.rune_results=[]
        for _ in range(count):
            r = roll_rune()
            import uuid
            r["id"] = str(uuid.uuid4())
            self.runes_inventory.append(r)
            self.rune_results.append(r)
        self.do_save(); self.draw_rune_gacha()

    # ── RUNE BOARD ──
    def goto_rune_board(self): self.state="rune_board"; self.rune_page = getattr(self, "rune_page", 0); self.draw_rune_board()
    def draw_rune_board(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#050510",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#1a1a2e",outline="#30363d")
        c.create_text(20,30,text="💠 Global Rune Board",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        
        c.create_text(WIDTH//2, 90, text="Equipped Global Runes", fill=GOLD, font=("Segoe UI", 14, "bold"))
        c.create_text(WIDTH//2, 110, text="These runes boost ALL characters in your party.", fill="#aaa", font=("Segoe UI", 10))
        
        slot_w = 180; slot_h = 100
        start_x = WIDTH//2 - (3*slot_w + 40)//2
        for i in range(3):
            x = start_x + i*(slot_w + 20); y = 130
            c.create_rectangle(x, y, x+slot_w, y+slot_h, fill="#161b22", outline="#444", width=2)
            c.create_text(x+10, y+15, text=f"Slot {i+1}", fill="#aaa", font=("Segoe UI", 10, "bold"), anchor="w")
            
            r = self.equipped_runes[i]
            if r:
                c.create_text(x+slot_w//2, y+40, text=r["icon"], font=("Segoe UI Emoji", 24))
                c.create_text(x+slot_w//2, y+70, text=r["name"], fill=r["color"], font=("Segoe UI", 10, "bold"))
                c.create_text(x+slot_w//2, y+85, text=r["desc"], fill=GREEN, font=("Segoe UI", 9))
                self.add_btn(x+slot_w-45, y+5, 40, 20, "X", RED, font_size=8, command=lambda idx=i: self._unequip_rune(idx))
            else:
                c.create_text(x+slot_w//2, y+slot_h//2, text="EMPTY", fill="#555", font=("Segoe UI", 14, "bold"))
                
        c.create_rectangle(20, 260, WIDTH-20, HEIGHT-70, fill="#0b0b1a", outline="#30363d")
        c.create_text(40, 280, text="Rune Inventory", fill=WHITE, font=("Segoe UI", 14, "bold"), anchor="w")
        
        # Ensure equipped runes are fully filtered by ID if available, else exact dict match
        eq_ids = [r.get("id") for r in self.equipped_runes if r and "id" in r]
        inv = [r for r in self.runes_inventory if r.get("id") not in eq_ids and (not eq_ids or r not in self.equipped_runes)]
        
        per_page = 10; start = self.rune_page * per_page
        subset = inv[start:start+per_page]
        
        if not inv:
            c.create_text(WIDTH//2, 400, text="No unequipped runes. Pull from Rune Summon!", fill="#888", font=("Segoe UI", 12))
        else:
            cw=160; ch_h=80
            for i, r in enumerate(subset):
                col=i%5; row=i//5
                x = 40 + col*(cw+10); y = 310 + row*(ch_h+10)
                c.create_rectangle(x, y, x+cw, y+ch_h, fill="#1a1a2e", outline=r["color"])
                c.create_text(x+15, y+25, text=r["icon"], font=("Segoe UI Emoji", 16))
                c.create_text(x+35, y+25, text=r["name"], fill=r["color"], font=("Segoe UI", 10, "bold"), anchor="w")
                c.create_text(x+cw//2, y+50, text=r["desc"], fill=GREEN, font=("Segoe UI", 9))
                self.add_btn(x+cw//2-30, y+60, 60, 20, "Equip", BLUE, font_size=8, command=lambda rune=r: self._equip_rune(rune))
                
        if self.rune_page > 0: self.add_btn(40, 480, 80, 30, "← Prev", "#333", command=lambda: self._page_runes(-1))
        if start+per_page < len(inv): self.add_btn(WIDTH-120, 480, 80, 30, "Next →", "#333", command=lambda: self._page_runes(1))
            
        self.add_btn(WIDTH//2-80, HEIGHT-50, 160, 35, "← Hub", GRAY, font_size=11, command=self.goto_hub)

    def _equip_rune(self, rune):
        for i in range(3):
            if self.equipped_runes[i] is None:
                self.equipped_runes[i] = rune
                self.do_save(); self.draw_rune_board()
                return
        self.notif_msg = "No empty slots! Unequip a rune first."; self.notif_timer = 60; self.draw_rune_board()
        
    def _unequip_rune(self, idx):
        self.equipped_runes[idx] = None
        self.do_save(); self.draw_rune_board()
        
    def _page_runes(self, d): self.rune_page += d; self.draw_rune_board()

    # ── PARTY ──
    def goto_party(self): self.state="party"; self.draw_party()
    def draw_party(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text=f"👥 Manage Party (max {self.get_max_party_size()})",fill=WHITE,font=("Segoe UI",14,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        if not self.owned_chars:
            c.create_text(WIDTH//2,HEIGHT//2,text="No characters yet!",fill="#888",font=("Segoe UI",16))
        else:
            # Sort: Party members first (by stars), then non-party members (by stars)
            sorted_owned = sorted(self.owned_chars, key=lambda c: (c not in self.party, -c.get("stars", 1), self.owned_chars.index(c)))
            cw=120; ch_h=140; cols=min(6,len(sorted_owned)); sx=(WIDTH-cols*(cw+10))//2
            tooltip_to_draw = None
            for i,ch in enumerate(sorted_owned):
                if i>=12: break
                col=i%6; row=i//6; x=sx+col*(cw+10); y=75+row*(ch_h+35)
                ip=ch in self.party; draw_card(c,x,y,cw,ch_h,ch,selected=ip)
                if ip: c.create_text(x+cw-10,y+10,text="✓",fill=GREEN,font=("Segoe UI",12,"bold"))
                self.add_btn(x,y+ch_h+2,cw-30,22,"Remove" if ip else "Add",GREEN if ip else ACCENT2,font_size=8,command=lambda ch=ch:self.toggle_party(ch))
                info_btn = self.add_btn(x+cw-25,y+ch_h+2,25,22,"i","#333",font_size=12,command=lambda:None)
                if getattr(info_btn, "is_hover", False):
                    sd = ch.get("skill_dmg", 1.5)
                    sn = ch.get("skill", "Skill")
                    info = f"Heal 200% ATK" if sd == 0 else f"{sn}: {int(sd*100)}% ATK"
                    tooltip_to_draw = (x, y+ch_h+25, cw, info)
                    
        self.add_btn(WIDTH//2-80,HEIGHT-50,160,38,"← Back",GRAY,font_size=11,command=self.goto_hub)
        
        # Draw tooltip on the very top layer
        if locals().get("tooltip_to_draw"):
            tx, ty, tcw, tinfo = tooltip_to_draw
            c.create_rectangle(tx-20, ty, tx+tcw+20, ty+20, fill="#2a2a4e", outline=PURPLE, width=1)
            c.create_text(tx+tcw//2, ty+10, text=tinfo, fill=WHITE, font=("Segoe UI", 9, "bold"))

    def toggle_party(self,char):
        if char in self.party: self.party.remove(char)
        elif len(self.party) < self.get_max_party_size(): self.party.append(char)
        self.do_save(); self.draw_party()

    # ── BACKPACK ──
    def goto_backpack(self): self.state="backpack"; self.bp_selected_char=None; self.bp_tab="loot"; self.bp_item_page=0; self.draw_backpack()
    def _set_bp_tab(self, tab): self.bp_tab = tab; self.bp_item_page = 0; self.draw_backpack()
    def draw_backpack(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text="🎒 Backpack & Level Up",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)

        def it_sort(k):
            it=ITEMS[k]; t=it["type"]; name=it["name"]
            tier=0
            if "_" in k:
                try: tier=int(k.split("_")[-1])
                except: pass
            return (t, name, tier)
        
        items_list = sorted([(k,v) for k,v in self.backpack.items() if v>0], key=lambda x: it_sort(x[0]))

        # Item Pagination
        per_page = 8; start = self.bp_item_page * per_page
        subset = items_list[start : start + per_page]
        
        if not items_list: c.create_text(30,120,text="Empty — win stages for loot!",fill="#888",font=("Segoe UI",11),anchor="w")
        iy=115
        for key,qty in subset:
            it=ITEMS[key]
            c.create_rectangle(20,iy,380,iy+38,fill=BG_CARD,outline=it["color"],width=1)
            c.create_text(35,iy+19,text=f"{it['icon']} {it['name']} x{qty}",fill=WHITE,font=("Segoe UI",10),anchor="w")
            c.create_text(370,iy+19,text=it["desc"],fill=it["color"],font=("Segoe UI",8),anchor="e")
            if self.bp_selected_char is not None:
                if it["type"]=="exp": self.add_btn(385,iy+4,55,30,"Use",GREEN,font_size=8,command=lambda k=key:self.use_item(k))
                elif it["type"]=="buff": self.add_btn(385,iy+4,55,30,"Use",BLUE,font_size=8,command=lambda k=key:self.use_buff(k))
            
            if it["type"] == "gold":
                self.add_btn(385,iy+4,55,30,"Open",GOLD,font_size=8,command=lambda k=key:self.use_item(k))
            iy+=44
            
        # Paging for Items
        if self.bp_item_page > 0:
            self.add_btn(20, 500, 70, 25, "← Prev", "#333", font_size=8, command=lambda: self._bp_it_p(-1))
        if start + per_page < len(items_list):
            self.add_btn(310, 500, 70, 25, "Next →", "#333", font_size=8, command=lambda: self._bp_it_p(1))
        c.create_text(500,80,text="Select Character:",fill=WHITE,font=("Segoe UI",13,"bold"),anchor="w")
        cy=105
        sorted_owned = sorted(self.owned_chars, key=lambda c: (c not in self.party, self.owned_chars.index(c)))
        for i,ch in enumerate(sorted_owned):
            if i>=8: break
            actual_idx = self.owned_chars.index(ch)
            sel=(self.bp_selected_char==actual_idx)
            is_p = ch in self.party
            # Highlight for party members
            bg_col = "#1a2a4e" if sel else ("#161b3e" if is_p else BG_CARD)
            out_col = GOLD if sel else (GREEN if is_p else "#333")
            c.create_rectangle(490,cy,870,cy+48,fill=bg_col,outline=out_col,width=2 if (sel or is_p) else 1)
            if is_p: c.create_text(855, cy+12, text="[DEPLOYED]", fill=GREEN, font=("Segoe UI", 7, "bold"), anchor="e")
            ac = len(ch.get("armors_equipped", [])) + ch.get("armor_count", 0)
            stars = ch.get("stars", 1)
            c.create_text(510,cy+14,text=f"{ch['icon']} {ch['name']} ★x{stars} (Armor: {ac}/4)",fill=WHITE,font=("Segoe UI",9,"bold"),anchor="w")
            lvl=ch.get("level",1); exp=ch.get("exp",0); needed=exp_for_level(lvl+1) if lvl<MAX_LEVEL else 0
            c.create_text(510,cy+34,text=f"Lv.{lvl} EXP:{exp}/{needed} HP:{ch['hp']} ATK:{ch['atk']}",fill="#aaa",font=("Segoe UI",7),anchor="w")
            if lvl<MAX_LEVEL: draw_bar(c,790,cy+10,70,10,exp/needed if needed else 1,CYAN,"#222")
            else: c.create_text(830,cy+15,text="MAX",fill=GOLD,font=("Segoe UI",8,"bold"))
            if sel and ac > 0:
                self.add_btn(770,cy+24,60,20,"Unequip",RED,font_size=7,command=lambda idx=actual_idx:self.unequip_armor(idx))
            self.add_btn(848,cy+24,20,20,"→",ACCENT2,font_size=7,command=lambda idx=actual_idx:self.bp_select(idx))
            cy+=54
        self.add_btn(WIDTH//2-80,HEIGHT-50,160,38,"← Back",GRAY,font_size=11,command=self.goto_hub)

    def _bp_it_p(self, d): self.bp_item_page += d; self.draw_backpack()
    def bp_select(self,idx): self.bp_selected_char=idx; self.draw_backpack()
    def use_item(self,key):
        if self.backpack.get(key,0)<=0: return
        it = ITEMS[key]
        
        if it["type"] == "gold":
            self.gold += it["value"]
            self.backpack[key] -= 1
            self.notif_msg = f"Opened {it['name']} for {it['value']} Gold!"; self.notif_timer = 40
            self.do_save(); self.draw_backpack()
            return

        if self.bp_selected_char is None: return
        ch=self.owned_chars[self.bp_selected_char]
        if ch.get("level",1)>=MAX_LEVEL: self.draw_backpack(); return
        it=ITEMS[key]
        
        max_q = self.backpack[key]
        
        # Custom Slider Dialog
        top = tk.Toplevel(self.root)
        top.title("Use Potion")
        
        # Spawn near mouse
        mx = self.root.winfo_pointerx()
        my = self.root.winfo_pointery()
        top.geometry(f"300x200+{mx-150}+{my-100}")
        
        top.configure(bg="#1a1a2e")
        top.transient(self.root); top.grab_set()
        
        tk.Label(top, text=f"Use {it['name']}", fg="white", bg="#1a1a2e", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        val_var = tk.IntVar(value=1)
        # Slider
        scale = tk.Scale(top, from_=1, to=max_q, orient="horizontal", variable=val_var, 
                         bg="#1a1a2e", fg="white", highlightthickness=0, troughcolor="#333", activebackground=ACCENT)
        scale.pack(fill="x", padx=30, pady=5)
        
        lbl_info = tk.Label(top, text=f"Quantity: 1\nExp: {it['value']}", fg=GOLD, bg="#1a1a2e", font=("Segoe UI", 10))
        lbl_info.pack(pady=5)
        
        def update_info(*args):
            q = val_var.get()
            lbl_info.config(text=f"Quantity: {q}\nExp: {it['value'] * q}")
        val_var.trace_add("write", update_info)
        
        def confirm():
            qty = val_var.get()
            top.destroy()
            self._process_use_item(ch, key, qty, it)
            
        tk.Button(top, text="CONFIRM", command=confirm, bg=GREEN, fg="white", font=("Segoe UI", 10, "bold"), width=15).pack(pady=10)

    def _process_use_item(self, ch, key, qty, it):
        if not qty or qty <= 0: return
        
        self.backpack[key] -= qty
        total_exp = it["value"] * qty
        from game.constants import add_exp
        gained = add_exp(ch, total_exp)
        self.do_save(); self.draw_backpack()
        msg=f"✨ +{total_exp} EXP"
        if gained>0: msg+=f" — LEVEL UP! (+{gained})"
        self.notif_msg = msg; self.notif_timer = 60

    def use_buff(self,key):
        if self.bp_selected_char is None or self.backpack.get(key,0)<=0: return
        ch=self.owned_chars[self.bp_selected_char]; cid=id(ch)
        if cid not in self.active_buffs: self.active_buffs[cid]=[]
        self.active_buffs[cid].append(key); self.backpack[key]-=1; self.do_save(); self.draw_backpack()
        self.notif_msg = "🧪 Buff Applied for Next Battle!"; self.notif_timer = 60

    def equip_armor(self, key):
        if self.bp_selected_char is None or self.backpack.get(key,0)<=0: return
        ch=self.owned_chars[self.bp_selected_char]
        ac = len(ch.get("armors_equipped", [])) + ch.get("armor_count", 0)
        if ac < 4:
            if "armors_equipped" not in ch: ch["armors_equipped"] = []
            ch["armors_equipped"].append(key)
            self.backpack[key] -= 1
            from game.constants import update_char_stats, ITEMS
            update_char_stats(ch)
            self.do_save(); self.draw_backpack()
            self.notif_msg = f"⚔️ {ITEMS[key]['name']} Equipped!"; self.notif_timer = 60

    def unequip_armor(self, idx):
        ch = self.owned_chars[idx]
        if "armors_equipped" in ch and len(ch["armors_equipped"]) > 0:
            key = ch["armors_equipped"].pop()
            self.backpack[key] = self.backpack.get(key, 0) + 1
        elif ch.get("armor_count", 0) > 0:
            ch["armor_count"] -= 1
            self.backpack["boss_armor"] = self.backpack.get("boss_armor", 0) + 1
        else:
            return
        from game.constants import update_char_stats
        update_char_stats(ch); self.do_save(); self.draw_backpack()
        self.canvas.create_text(WIDTH//2,HEIGHT-80,text="Armor Unequipped!",fill=GREEN,font=("Segoe UI",14, "bold"))

    # ── STAGES ──
    def goto_stages(self): self.state="stages"; self.stage_page=self.max_stage_cleared // 4; self.draw_stages()
    def draw_stages(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text=f"⚔️ Stages (Cleared: {self.max_stage_cleared})",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"Page {self.stage_page+1}  🎟️ {self.backpack.get('skip_ticket', 0)}",fill="#aaa",font=("Segoe UI",12),anchor="e")
        
        if not self.party:
            c.create_text(WIDTH//2,HEIGHT//2,text="Add characters to party first!",fill=RED,font=("Segoe UI",16))
            self.add_btn(WIDTH//2-80,HEIGHT//2+40,160,38,"← Back",GRAY,font_size=11,command=self.goto_hub); return
        colors=["#1b5e20","#4e342e","#bf360c","#4a148c","#1a237e","#880e4f","#004d40","#e65100"]
        start=self.stage_page*4
        for j in range(4):
            i=start+j; stg=get_stage(i); y=75+j*120; col=colors[i%len(colors)]
            locked = i > self.max_stage_cleared
            fill_c = "#111118" if locked else BG_CARD
            c.create_rectangle(80,y,WIDTH-80,y+100,fill=fill_c,outline=col if not locked else "#333",width=2)
            if locked:
                c.create_text(WIDTH//2,y+35,text=f"🔒 Stage {i+1}: {stg['name']}",fill="#555",font=("Segoe UI",14,"bold"))
                c.create_text(WIDTH//2,y+60,text=f"Clear Stage {i} to unlock",fill="#444",font=("Segoe UI",10))
            else:
                tag = "✅ " if i < self.max_stage_cleared else ""
                c.create_text(110,y+25,text=f"{tag}Stage {i+1}: {stg['name']}",fill=WHITE,font=("Segoe UI",14,"bold"),anchor="w")
                from game.constants import get_stage_gold_reward
                reward = get_stage_gold_reward(i)
                c.create_text(110,y+50,text=f"Enemies: {len(stg['enemies'])} | Reward: {reward:,}g + Loot",fill="#aaa",font=("Segoe UI",10),anchor="w")
                if i>=len(FIXED_STAGES):
                    c.create_text(110,y+72,text="∞ Infinite Stage",fill=CYAN,font=("Segoe UI",9),anchor="w")
                
                # Button positions adjusted for better centering/balance
                self.add_btn(WIDTH-200,y+30,100,40,"FIGHT!",col,font_size=13,command=lambda idx=i:self.start_battle(idx))
                if i < self.max_stage_cleared:
                    self.add_btn(WIDTH-310,y+30,100,40,"🎟️ SKIP",PURPLE,font_size=11,command=lambda idx=i:self.use_skip_ticket(idx))
        if self.stage_page > 0:
            self.add_btn(WIDTH//2-170,HEIGHT-50,100,38,"← Prev",ACCENT2,font_size=11,command=lambda:self._sp(-1))
        self.add_btn(WIDTH//2-40,HEIGHT-50,80,38,"← Hub",GRAY,font_size=10,command=self.goto_hub)
        if start+4 <= self.max_stage_cleared+1:
            self.add_btn(WIDTH//2+70,HEIGHT-50,100,38,"Next →",ACCENT2,font_size=11,command=lambda:self._sp(1))
            
        # AFK Button
        self.add_btn(20, HEIGHT-50, 130, 38, "🏠 AFK Area", "#2e7d32", font_size=11, command=self.goto_afk)
        # Dungeon Button
        self.add_btn(WIDTH-170, HEIGHT-50, 150, 38, "⚔️ DUNGEON", "#8b0000", font_size=11, command=self.goto_dungeon)

    def _sp(self,d): self.stage_page=max(0,self.stage_page+d); self.draw_stages()

    def use_skip_ticket(self, idx):
        if self.backpack.get("skip_ticket", 0) <= 0:
            self.draw_stages()
            self.canvas.create_text(WIDTH//2, HEIGHT-80, text="No Skip Tickets left!", fill=RED, font=("Segoe UI", 14, "bold"))
            return
        self.backpack["skip_ticket"] -= 1
        from game.constants import get_stage_gold_reward
        reward = get_stage_gold_reward(idx); self.gold += reward
        loot = roll_loot(idx, include_ticket=False)
        from collections import Counter
        loot_counts = Counter(loot)
        for k in loot:
            if ITEMS[k]["type"]=="gold":
                bag_mult = 1 + (idx // 5) * 0.2
                self.gold += int(ITEMS[k]["value"] * bag_mult)
            else: self.backpack[k] = self.backpack.get(k, 0) + 1
        self.do_save(); self.draw_stages()
        
        loot_str = ", ".join([f"{count}x {ITEMS[k]['icon']}" for k, count in loot_counts.items()])
        self.notif_msg = f"Skipped Stage {idx+1}! +{reward}g" + (f" and Loot: {loot_str}" if loot_str else "")
        self.notif_timer = 60 # ~3 seconds at 20fps

    # ── DUNGEON ──
    def goto_dungeon(self):
        self.state = "dungeon"; self.dungeon_page = 0; self.draw_dungeon()

    def draw_dungeon(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0a0008",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#2d0a0a",outline="#5c1010")
        c.create_text(20,30,text="⚔️ Dungeon — Gear Farming",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"🔨 {self.backpack.get('forge_stone',0)}",fill=ORANGE,font=("Segoe UI",14),anchor="e")
        
        if not self.party:
            c.create_text(WIDTH//2,HEIGHT//2,text="Add characters to party first!",fill=RED,font=("Segoe UI",16))
            self.add_btn(WIDTH//2-80,HEIGHT//2+40,160,38,"← Back",GRAY,font_size=11,command=self.goto_stages); return
        
        from game.constants import generate_dungeon_stage
        start = self.dungeon_page * 4
        for j in range(4):
            floor = start + j; y = 75 + j * 120
            locked = floor > getattr(self, "max_dungeon_cleared", 0)
            stg = generate_dungeon_stage(floor)
            fill_c = "#111118" if locked else "#1a0a0a"
            c.create_rectangle(80,y,WIDTH-80,y+100,fill=fill_c,outline="#8b0000" if not locked else "#333",width=2)
            if locked:
                c.create_text(WIDTH//2,y+35,text=f"🔒 Floor {floor+1}",fill="#555",font=("Segoe UI",14,"bold"))
                c.create_text(WIDTH//2,y+60,text=f"Clear Floor {floor} to unlock",fill="#444",font=("Segoe UI",10))
            else:
                tag = "✅ " if floor < getattr(self, "max_dungeon_cleared", 0) else ""
                mult = 2 ** (floor + 1)
                c.create_text(110,y+20,text=f"{tag}Floor {floor+1}: {stg['name']}",fill=WHITE,font=("Segoe UI",14,"bold"),anchor="w")
                c.create_text(110,y+45,text=f"Enemies: {len(stg['enemies'])}  |  x{mult} Difficulty  |  Gear: T{floor+1}",fill="#aaa",font=("Segoe UI",10),anchor="w")
                c.create_text(110,y+65,text=f"Drops: T{floor+1} Gear + Forge Stones",fill=ORANGE,font=("Segoe UI",9),anchor="w")
                self.add_btn(WIDTH-200,y+30,100,40,"FIGHT!","#8b0000",font_size=13,command=lambda f=floor:self.start_dungeon_battle(f))
                
        if self.dungeon_page > 0:
            self.add_btn(WIDTH//2-170,HEIGHT-50,100,38,"← Prev",ACCENT2,font_size=11,command=lambda:self._dp(-1))
        self.add_btn(WIDTH//2-40,HEIGHT-50,80,38,"← Stages",GRAY,font_size=10,command=self.goto_stages)
        if start+4 <= getattr(self, "max_dungeon_cleared", 0) + 1:
            self.add_btn(WIDTH//2+70,HEIGHT-50,100,38,"Next →",ACCENT2,font_size=11,command=lambda:self._dp(1))

    def _dp(self, d): self.dungeon_page = max(0, self.dungeon_page + d); self.draw_dungeon()

    def start_dungeon_battle(self, floor):
        from game.constants import generate_dungeon_stage
        self.current_dungeon_floor = floor
        stg = generate_dungeon_stage(floor)
        self.start_battle_with_stage(stg, is_dungeon=True)

    def start_battle_with_stage(self, stage_data, is_dungeon=False):
        self.state = "battle"
        self.current_stage = stage_data
        self.stage_idx = -1 if is_dungeon else getattr(self, "stage_idx", 0)
        self.is_dungeon_battle = is_dungeon
        from game.battle import BattleMixin
        BattleMixin.start_battle(self, self.stage_idx)

    # ── ARMORY ──
    def goto_armory(self):
        self.state = "armory"; self.armory_tab = "sword"; self.armory_sel_gear = None
        self.armory_page = 0; self.draw_armory()

    def _find_gear_owner(self, gear_id):
        from game.constants import GEAR_SLOTS
        for ch in self.owned_chars:
            if "gear" not in ch: continue
            for s in GEAR_SLOTS:
                g = ch["gear"].get(s)
                if g and g.get("id") == gear_id:
                    return ch
        return None

    def draw_armory(self):
        self.clear(); c=self.canvas
        from game.constants import GEAR_SLOTS, GEAR_ICONS, get_gear_stats, gear_upgrade_cost
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#05050f",outline="")
        c.create_rectangle(0,0,WIDTH,60,fill="#1a1a2e",outline="#30363d")
        c.create_text(20,30,text="🗡️ Armory",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"🔨 {self.backpack.get('forge_stone',0)}  💰 {self.gold}",fill=GOLD,font=("Segoe UI",12),anchor="e")
        
        tab_names = {"helmet": "🪖 Helmet", "chestplate": "🛡️ Chest", "legging": "🦿 Leg", "boot": "👢 Boot", "sword": "⚔️ Sword"}
        tx = 20
        for slot in GEAR_SLOTS:
            col = ACCENT if self.armory_tab == slot else "#333"
            self.add_btn(tx, 68, 150, 30, tab_names[slot], col, font_size=9, command=lambda s=slot: self._set_armory_tab(s))
            tx += 160
        
        # Left Panel: Gear List
        c.create_rectangle(20, 110, 440, HEIGHT-60, fill="#0b0b1a", outline="#30363d")
        c.create_text(30, 125, text=f"Inventory: {tab_names[self.armory_tab]}", fill=WHITE, font=("Segoe UI", 12, "bold"), anchor="w")
        
        # Multi-select Toggle
        m_col = GREEN if self.armory_multi_mode else "#444"
        self.add_btn(300, 115, 130, 25, "Bulk Mode: " + ("ON" if self.armory_multi_mode else "OFF"), m_col, font_size=8, command=self._toggle_armory_multi_mode)
        
        tab_gear = [g for g in self.gear_inventory if g.get("slot") == self.armory_tab]
        per_page = 5; start = self.armory_page * per_page
        subset = tab_gear[start:start+per_page]
        
        gy = 145
        for i, gear in enumerate(subset):
            stats = get_gear_stats(gear)
            sel = (self.armory_sel_gear and self.armory_sel_gear.get("id") == gear.get("id"))
            owner = self._find_gear_owner(gear.get("id"))
            c.create_rectangle(30, gy, 430, gy+55, fill="#161b22" if not sel else "#1a2a4e", outline=gear["color"], width=2 if sel else 1)
            c.create_text(45, gy+15, text=gear["icon"], font=("Segoe UI Emoji", 14))
            c.create_text(70, gy+12, text=f"{gear['name']} Lv.{gear['level']}", fill=gear["color"], font=("Segoe UI", 10, "bold"), anchor="w")
            stat_str = "  ".join(f"+{v}% {k.replace('_pct','').replace('_',' ').upper()}" for k,v in stats.items())
            c.create_text(70, gy+32, text=stat_str, fill=GREEN, font=("Segoe UI", 8), anchor="w")
            if owner:
                c.create_text(420, gy+12, text=f"[{owner['name'][:8]}]", fill=CYAN, font=("Segoe UI", 7, "bold"), anchor="e")
            c.create_text(420, gy+30, text=gear["tier"], fill=gear["color"], font=("Segoe UI", 8, "bold"), anchor="e")
            
            if self.armory_multi_mode:
                is_sel = gear.get("id") in self.armory_selected_ids
                b_txt = "✅ SELECTED" if is_sel else "⬜ SELECT"
                b_col = GREEN if is_sel else "#444"
                self.add_btn(350, gy+38, 70, 15, b_txt, b_col, font_size=7, command=lambda g_id=gear.get("id"): self._toggle_gear_selection(g_id))
            else:
                self.add_btn(350, gy+38, 70, 15, "Select", BLUE, font_size=7, command=lambda g=gear: self._select_gear(g))
            gy += 62
            
        if not tab_gear:
            c.create_text(230, 300, text="No gear. Farm Dungeons!", fill="#555", font=("Segoe UI", 12))
            
        if self.armory_page > 0: self.add_btn(30, HEIGHT-80, 70, 25, "← Prev", "#333", font_size=8, command=lambda: self._armory_p(-1))
        if start+per_page < len(tab_gear): self.add_btn(380, HEIGHT-80, 70, 25, "Next →", "#333", font_size=8, command=lambda: self._armory_p(1))
        
        # Right Panel
        c.create_rectangle(460, 110, WIDTH-20, HEIGHT-60, fill="#0b0b1a", outline="#30363d")
        
        if self.armory_multi_mode:
            c.create_text(630, 150, text="BULK SALVAGE MODE", fill=GOLD, font=("Segoe UI", 16, "bold"))
            count = len(self.armory_selected_ids)
            c.create_text(630, 180, text=f"Selected: {count} items", fill=WHITE, font=("Segoe UI", 12))
            
            if count > 0:
                total_return = 0
                for g_id in self.armory_selected_ids:
                    g = next((x for x in self.gear_inventory if x.get("id") == g_id), None)
                    if g: total_return += max(1, g.get("level", 1))
                
                c.create_text(630, 210, text=f"Total Return: {total_return} 🔨", fill=GREEN, font=("Segoe UI", 11, "bold"))
                self.add_btn(530, 250, 200, 45, f"🗑️ SALVAGE ALL ({count})", "#b71c1c", font_size=12, command=self._bulk_salvage_gears)
            else:
                c.create_text(630, 250, text="Select items from the left\nto salvage in bulk.", fill="#777", font=("Segoe UI", 11))
                
        elif self.armory_sel_gear:
            gear = self.armory_sel_gear
            stats = get_gear_stats(gear)
            c.create_text(630, 130, text=f"{gear['icon']} {gear['name']}", fill=gear["color"], font=("Segoe UI", 14, "bold"))
            c.create_text(630, 155, text=f"Tier: {gear['tier']}  |  Level: {gear['level']}", fill="#aaa", font=("Segoe UI", 10))
            
            sy = 180
            for k, v in stats.items():
                label = k.replace("_pct","").replace("_"," ").upper()
                c.create_text(490, sy, text=f"+{v}% {label}", fill=GREEN, font=("Segoe UI", 11), anchor="w")
                sy += 22
                
            cost = gear_upgrade_cost(gear)
            can_up = self.backpack.get("forge_stone", 0) >= cost["forge_stone"] and self.gold >= cost["gold"]
            if "crit_chance" in stats and stats["crit_chance"] >= 70:
                c.create_text(630, sy+5, text="⚠️ Crit near cap (75%)", fill=ORANGE, font=("Segoe UI", 9)); sy += 20
                
            self.add_btn(490, sy+5, 130, 30, f"🔨 Upgrade (🔨{cost['forge_stone']} 💰{cost['gold']})", ORANGE if can_up else "#333", font_size=8, command=lambda: self._upgrade_gear())
            salvage_return = max(1, gear['level'])
            self.add_btn(630, sy+5, 120, 30, f"🗑️ Salvage (+{salvage_return}🔨)", "#b71c1c", font_size=8, command=lambda: self._salvage_gear())
            
            owner = self._find_gear_owner(gear.get("id"))
            if owner:
                c.create_text(630, sy+50, text=f"Equipped by: {owner['icon']} {owner['name']}", fill=CYAN, font=("Segoe UI", 11, "bold"))
                self.add_btn(490, sy+65, 180, 28, "❌ Unequip", RED, font_size=9, command=lambda: self._unequip_gear())
                sy += 100
            else:
                c.create_text(580, sy+50, text="Equip to (Party):", fill=WHITE, font=("Segoe UI", 11, "bold"), anchor="w")
                cy2 = sy + 70
                for ch in self.party:
                    eq = ch.get("gear", {}).get(self.armory_tab)
                    eq_txt = f" [{eq['name'][:8]}]" if eq else ""
                    idx = self.owned_chars.index(ch)
                    self.add_btn(480, cy2, 220, 22, f"{ch['icon']} {ch['name']}{eq_txt}", "#333", font_size=8, command=lambda i=idx: self._equip_gear_to_char(i))
                    cy2 += 26
        else:
            c.create_text(630, 300, text="Select a gear piece\nfrom the left panel", fill="#555", font=("Segoe UI", 12), justify="center")
            
        self.add_btn(WIDTH//2-80, HEIGHT-50, 160, 35, "← Hub", GRAY, font_size=11, command=self.goto_hub)

    def _set_armory_tab(self, tab): self.armory_tab = tab; self.armory_sel_gear = None; self.armory_page = 0; self.draw_armory()
    def _select_gear(self, gear): self.armory_sel_gear = gear; self.draw_armory()
    def _armory_p(self, d): self.armory_page += d; self.draw_armory()
    
    def _upgrade_gear(self):
        if not self.armory_sel_gear: return
        from game.constants import gear_upgrade_cost
        gear = self.armory_sel_gear
        cost = gear_upgrade_cost(gear)
        if self.backpack.get("forge_stone", 0) < cost["forge_stone"] or self.gold < cost["gold"]:
            self.notif_msg = "Not enough materials!"; self.notif_timer = 40; self.draw_armory(); return
        self.backpack["forge_stone"] = self.backpack.get("forge_stone", 0) - cost["forge_stone"]
        self.gold -= cost["gold"]
        gear["level"] += 1
        for g in self.gear_inventory:
            if g.get("id") == gear.get("id"): g["level"] = gear["level"]; break
        # Update in equipped chars too
        owner = self._find_gear_owner(gear.get("id"))
        if owner and owner.get("gear", {}).get(gear["slot"]):
            owner["gear"][gear["slot"]]["level"] = gear["level"]
        self.do_save()
        self.notif_msg = f"Upgraded to Lv.{gear['level']}!"; self.notif_timer = 40
        self.draw_armory()

    def _salvage_gear(self):
        if not self.armory_sel_gear: return
        gear = self.armory_sel_gear
        # Unequip first if equipped
        owner = self._find_gear_owner(gear.get("id"))
        if owner:
            from game.constants import GEAR_SLOTS
            if "gear" not in owner: owner["gear"] = {s: None for s in GEAR_SLOTS}
            owner["gear"][gear["slot"]] = None
        # Calculate return: gear level worth of forge stones
        stones_back = max(1, gear.get("level", 1))
        self.backpack["forge_stone"] = self.backpack.get("forge_stone", 0) + stones_back
        # Remove from inventory
        self.gear_inventory = [g for g in self.gear_inventory if g.get("id") != gear.get("id")]
        self.armory_sel_gear = None
        self.do_save()
        self.notif_msg = f"Salvaged {gear['name']}! +{stones_back} 🔨"; self.notif_timer = 40
        self.draw_armory()

    def _unequip_gear(self):
        if not self.armory_sel_gear: return
        gear = self.armory_sel_gear
        owner = self._find_gear_owner(gear.get("id"))
        if owner:
            from game.constants import GEAR_SLOTS
            if "gear" not in owner: owner["gear"] = {s: None for s in GEAR_SLOTS}
            owner["gear"][gear["slot"]] = None
            self.do_save()
            self.notif_msg = f"Unequipped {gear['name']}!"; self.notif_timer = 40
        self.draw_armory()

    def _equip_gear_to_char(self, char_idx):
        if not self.armory_sel_gear: return
        from game.constants import GEAR_SLOTS
        gear = self.armory_sel_gear
        # Unequip from previous owner first
        prev_owner = self._find_gear_owner(gear.get("id"))
        if prev_owner:
            if "gear" not in prev_owner: prev_owner["gear"] = {s: None for s in GEAR_SLOTS}
            prev_owner["gear"][gear["slot"]] = None
        # Equip to new char
        ch = self.owned_chars[char_idx]
        if "gear" not in ch: ch["gear"] = {s: None for s in GEAR_SLOTS}
        ch["gear"][gear["slot"]] = gear
        self.do_save()
        self.notif_msg = f"Equipped {gear['name']} to {ch['name']}!"; self.notif_timer = 40
        self.draw_armory()

    # ── ACHIEVEMENTS ──
    def goto_achievements(self): self.state="achievements"; self.draw_achievements()
    def draw_achievements(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text="🏆 Achievements & Perks",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        
        y=100
        unlocked = self.max_stage_cleared >= 50
        col = GOLD if unlocked else "#444"
        icon = "✅" if unlocked else "🔒"
        c.create_rectangle(50, y, WIDTH-50, y+80, fill=BG_CARD, outline=col, width=2)
        c.create_text(80, y+25, text=f"{icon} Vanguard (Clear Stage 50)", fill=WHITE if unlocked else "#888", font=("Segoe UI", 14, "bold"), anchor="w")
        c.create_text(80, y+55, text="Unlocks a 4th slot in your Party.", fill=GOLD if unlocked else "#666", font=("Segoe UI", 11), anchor="w")

        self.add_btn(WIDTH//2-80,HEIGHT-50,160,38,"← Back",GRAY,font_size=11,command=self.goto_hub)

    # ── ASCENSION ──
    def goto_ascension(self): self.state="ascension"; self.asc_page=0; self.draw_ascension()
    def draw_ascension(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text="🌟 Character Ascension",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        
        if not self.owned_chars:
            c.create_text(WIDTH//2,HEIGHT//2,text="No characters yet!",fill="#888",font=("Segoe UI",16))
        else:
            sorted_chars = sorted(self.owned_chars, key=lambda c: (c not in self.party, -c.get("stars", 1), self.owned_chars.index(c)))
            start = self.asc_page * 8
            for i in range(8):
                idx = start + i
                if idx >= len(sorted_chars): break
                ch = sorted_chars[idx]
                is_p = ch in self.party
                col = i%2; row = i//2
                x = 20 + col*430; y = 80 + row*100
                # Highlight party
                c.create_rectangle(x, y, x+410, y+90, fill="#161b3e" if is_p else BG_CARD, outline=GREEN if is_p else "#333", width=2 if is_p else 1)
                if is_p: c.create_text(x+405, y+10, text="DEPLOYED", fill=GREEN, font=("Segoe UI", 7, "bold"), anchor="ne")
                
                c.create_oval(x+10, y+15, x+70, y+75, fill=ch.get("color", ACCENT), outline="")
                c.create_text(x+40, y+45, text=ch.get("icon", "?"), font=("Segoe UI Emoji", 24))
                
                asc = ch.get("ascension", 0)
                req = 3 ** asc
                av = self.shards.get(ch["name"], 0)
                stars = ch.get("stars", 1)
                c.create_text(x+85, y+20, text=f"{ch['name']} ★x{stars} (Ascension {asc})", fill=WHITE, font=("Segoe UI", 12, "bold"), anchor="w")
                c.create_text(x+85, y+45, text=f"Shards: {av} / {req}", fill=GREEN if av>=req else RED, font=("Segoe UI", 10), anchor="w")
                mult = int((1.2 ** asc) * 100)
                next_m = int((1.2 ** (asc+1)) * 100)
                c.create_text(x+85, y+65, text=f"Stat Multiplier: {mult}% → {next_m}%", fill=GOLD, font=("Segoe UI", 9), anchor="w")
                
                if av >= req:
                    self.add_btn(x+300, y+25, 90, 40, "Ascend!", GOLD, font_size=11, command=lambda ch=ch, req=req:self.do_ascend(ch, req))
                else:
                    self.add_btn(x+300, y+25, 90, 40, "Locked", "#444", font_size=11)

            if self.asc_page > 0: self.add_btn(WIDTH//2-120,HEIGHT-50,100,38,"← Prev",ACCENT2,font_size=11,command=lambda:self._asc_p(-1))
            if start+8 < len(sorted_chars): self.add_btn(WIDTH//2+20,HEIGHT-50,100,38,"Next →",ACCENT2,font_size=11,command=lambda:self._asc_p(1))
            
        self.add_btn(20,HEIGHT-50,100,38,"← Back",GRAY,font_size=11,command=self.goto_hub)

    def _asc_p(self, d): self.asc_page+=d; self.draw_ascension()
    def do_ascend(self, ch, req):
        self.shards[ch["name"]] -= req
        ch["ascension"] = ch.get("ascension", 0) + 1
        from game.constants import update_char_stats
        update_char_stats(ch)
        self.do_save(); self.draw_ascension()
        self.canvas.create_text(WIDTH//2, HEIGHT-80, text=f"{ch['name']} ascended! Stats x1.2!", fill=GOLD, font=("Segoe UI", 16, "bold"))

    def _toggle_armory_multi_mode(self):
        self.armory_multi_mode = not self.armory_multi_mode
        self.armory_selected_ids = set()
        self.draw_armory()

    def _toggle_gear_selection(self, gear_id):
        if gear_id in self.armory_selected_ids:
            self.armory_selected_ids.remove(gear_id)
        else:
            self.armory_selected_ids.add(gear_id)
        self.draw_armory()

    def _bulk_salvage_gears(self):
        if not self.armory_selected_ids: return
        total_stones = 0
        from game.constants import GEAR_SLOTS
        to_remove = list(self.armory_selected_ids)
        for g_id in to_remove:
            gear = next((x for x in self.gear_inventory if x.get("id") == g_id), None)
            if not gear: continue
            owner = self._find_gear_owner(g_id)
            if owner:
                if "gear" not in owner: owner["gear"] = {s: None for s in GEAR_SLOTS}
                owner["gear"][gear["slot"]] = None
            total_stones += max(1, gear.get("level", 1))
            self.gear_inventory = [g for g in self.gear_inventory if g.get("id") != g_id]
        self.backpack["forge_stone"] = self.backpack.get("forge_stone", 0) + total_stones
        self.armory_selected_ids = set(); self.armory_multi_mode = False; self.armory_sel_gear = None
        self.do_save(); self.notif_msg = f"Bulk Salvaged {len(to_remove)} items! +{total_stones} \U0001f528"; self.notif_timer = 50
        self.draw_armory()
