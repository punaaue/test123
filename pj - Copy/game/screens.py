import random, copy, math
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
        self.active_buffs = {}; self.state = "menu"; self.anim_frame = 0
        self.stage_page = 0; self.bp_selected_char = None; self.max_stage_cleared = 0
        self.gacha_results = []; self.gacha_mode = "normal"; self.runes_equipped = [None, None, None]
        self._try_load()
        self.canvas.bind("<Button-1>", self.on_click); self.canvas.bind("<Motion>", self.on_motion)
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Escape>", lambda e: self.toggle_fullscreen() if getattr(self, "is_fullscreen", False) else None)
        self.draw_menu(); self.animate()

    def _try_load(self):
        data = load_game()
        if data:
            self.gold = data.get("gold", 500)
            self.backpack = data.get("backpack", {"exp_potion_1": 3})
            self.max_stage_cleared = data.get("max_stage_cleared", 0)
            self.runes_equipped = data.get("runes_equipped", [None, None, None])
            self.owned_chars = data.get("owned_chars", [])
            self.shards = data.get("shards", {})
            party_indices = data.get("party_indices", [])
            self.party = [self.owned_chars[i] for i in party_indices if i < len(self.owned_chars)]
            self.refresh_all_stats()

    def do_save(self):
        party_idx = [self.owned_chars.index(c) for c in self.party if c in self.owned_chars]
        save_game({"gold": self.gold, "backpack": self.backpack, "max_stage_cleared": self.max_stage_cleared,
                   "runes_equipped": self.runes_equipped,
                   "owned_chars": self.owned_chars, "party_indices": party_idx, "shards": getattr(self, "shards", {})})

    def do_reset(self):
        delete_save(); self.owned_chars=[]; self.party=[]; self.gold=500
        self.backpack={"exp_potion_1":3}; self.max_stage_cleared=0; self.active_buffs={}; self.shards={}
        self.goto_hub()

    def animate(self):
        self.anim_frame += 1
        if self.state == "menu": self.draw_menu()
        elif self.state == "battle":
            if hasattr(self, "_update_particles"): self._update_particles()
            if getattr(self, "b_shake", 0) > 0: self.b_shake -= 2
            if getattr(self, "b_flash", None): self.b_flash = None # Flash lasts 1 frame
            self.draw_battle()
        elif self.state == "stages":
            self.draw_stages()
        elif self.state == "runes":
            self.draw_runes()
            
        if getattr(self, "notif_timer", 0) > 0:
            self.notif_timer -= 1
            if self.notif_timer <= 0: self.notif_msg = None
            
        self.root.after(50, self.animate)

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
        c=self.canvas; c.delete("all"); self.buttons=[]; f=self.anim_frame
        for i in range(20):
            px=(i*47+f*(1+i%3))%WIDTH; py=(i*31+f*(2+i%2))%HEIGHT
            c.create_oval(px-2,py-2,px+2,py+2,fill=ACCENT,outline="")
        off=math.sin(f*0.1)*5
        c.create_text(WIDTH//2,170+off,text="⚔️ GACHA QUEST ⚔️",fill=GOLD,font=("Segoe UI",42,"bold"))
        c.create_text(WIDTH//2,230,text="Turn-Based RPG",fill="#888",font=("Segoe UI",14))
        self.add_btn(WIDTH//2-100,300,200,55,"▶  START",ACCENT,command=self.goto_hub)
        self.add_btn(WIDTH//2-100,375,200,55,"✕  QUIT",GRAY,command=self.root.destroy)

    # ── HUB ──
    def goto_hub(self): self.state="hub"; self.draw_hub()
    def back_menu(self): self.state="menu"; self.anim_frame=0

    def draw_hub(self):
        self.clear(); c=self.canvas
        # Premium Background with Grid
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0a0a20",outline="")
        for i in range(12): 
            c.create_line(0, i*50, WIDTH, i*50, fill="#16163a", width=1)
            c.create_line(i*80, 0, i*80, HEIGHT, fill="#16163a", width=1)
            
        # Top Header Bar
        c.create_rectangle(0,0,WIDTH,60,fill="#161b22",outline="#30363d")
        c.create_text(70,30,text="⚔️ Gacha Quest",fill=WHITE,font=("Segoe UI",18,"bold"),anchor="w")
        self.add_btn(20, 15, 30, 30, "🏆", GOLD, font_size=12, command=self.goto_achievements)
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"💰 {self.gold}  🎟️ {self.backpack.get('skip_ticket', 0)}",fill=GOLD,font=("Segoe UI",14),anchor="e")
        
        # Center Content Panel
        c.create_rectangle(WIDTH//2-220, 90, WIDTH//2+220, 520, fill="#161b22", outline="#30363d", width=2)
        c.create_text(WIDTH//2,130,text="COMMAND CENTER",fill=WHITE,font=("Segoe UI",20,"bold"))
        c.create_text(WIDTH//2,155,text=f"Stage: {self.max_stage_cleared} • Party: {len(self.party)} • Total Heroes: {len(self.owned_chars)}",fill="#888",font=("Segoe UI",10))

        # Grid Buttons (2 Columns)
        bx1 = WIDTH//2 - 195; bx2 = WIDTH//2 + 5; bw = 190; bh = 60
        # Row 1: Battle Actions
        self.add_btn(bx1, 185, bw, bh, "⚔️ STAGES", "#1a237e", font_size=13, command=self.goto_stages)
        self.add_btn(bx2, 185, bw, bh, "🌟 RUNES", "#4a148c", font_size=13, command=self.goto_runes)
        # Row 2: Management
        self.add_btn(bx1, 255, bw, bh, "🎰 GACHA", "#4e342e", font_size=13, command=self.goto_gacha)
        self.add_btn(bx2, 255, bw, bh, "👥 PARTY", "#1b5e20", font_size=13, command=self.goto_party)
        # Row 3: Growth
        self.add_btn(bx1, 325, bw, bh, "🎒 BACKPACK", "#e65100", font_size=13, command=self.goto_backpack)
        self.add_btn(bx2, 325, bw, bh, "🆙 ASCEND", "#f57f17", font_size=13, command=self.goto_ascension)
        
        # Footer Actions
        uy = 425
        self.add_btn(WIDTH//2-100, uy, 200, 42, "💾 QUICK SAVE", "#2196f3", font_size=11, command=self._save_notify)
        self.add_btn(WIDTH//2-100, uy+52, 200, 32, "↩ TITLE MENU", "#444", font_size=10, command=self.back_menu)
        
        # discreet Reset
        self.add_btn(WIDTH-100, HEIGHT-35, 80, 22, "Reset Data", "#331111", font_size=8, command=self.do_reset)

    def _save_notify(self):
        self.do_save()
        self.canvas.create_rectangle(WIDTH//2-100, HEIGHT-120, WIDTH//2+100, HEIGHT-80, fill="#1a1a2e", outline=GREEN, width=2)
        self.canvas.create_text(WIDTH//2, HEIGHT-100, text="💾 Progress Saved!", fill=GREEN, font=("Segoe UI", 10, "bold"))
        self.root.after(1500, self.draw_hub)

    # ── GACHA ──
    def goto_gacha(self): self.state="gacha"; self.gacha_results=[]; self.gacha_mode="normal"; self.draw_gacha()

    def draw_gacha(self):
        self.clear(); c=self.canvas
        # Gacha Background (Deep Space with stars)
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#100a1a",outline="")
        for i in range(30):
            rx, ry = random.randint(0,WIDTH), random.randint(0,HEIGHT)
            sz = random.randint(1,2)
            c.create_oval(rx, ry, rx+sz, ry+sz, fill=random.choice([PURPLE, GOLD, WHITE]), outline="")
            
        c.create_rectangle(0,0,WIDTH,60,fill="#1a1a2e",outline="#30363d")
        c.create_text(20,30,text="🎰 Celestial Gacha",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"💰 {self.gold} Gold",fill=GOLD,font=("Segoe UI",14),anchor="e")
        # Mode tabs
        nc="#5c2d91" if self.gacha_mode=="normal" else "#333"
        hc="#b71c1c" if self.gacha_mode=="high" else "#333"
        self.add_btn(100,70,200,35,"Normal (1-6★)",nc,font_size=11,command=lambda:self._set_gacha("normal"))
        self.add_btn(320,70,200,35,f"High Tier (4-10★)",hc,font_size=11,command=lambda:self._set_gacha("high"))
        # Show rates
        is_hi = self.gacha_mode=="high"
        rates = HIGH_RATES if is_hi else NORMAL_RATES
        cost = HIGH_COST if is_hi else NORMAL_COST
        rate_str = "  ".join(f"{s}★:{r}%" for s,r in rates.items())
        c.create_text(WIDTH//2,125,text=f"Cost: {cost}g | Rates: {rate_str}",fill="#aaa",font=("Segoe UI",8))
        # Results
        if self.gacha_results:
            cw=110; ch_h=130
            cols=min(5,len(self.gacha_results)); sx=(WIDTH-cols*(cw+8))//2
            for i,ch in enumerate(self.gacha_results):
                col=i%5; row=i//5; x=sx+col*(cw+8); y=145+row*(ch_h+8)
                draw_card(c,x,y,cw,ch_h,ch)
                txt = f"{ch['rarity']}" + (" (Dup)" if ch.get("is_duplicate") else "")
                c.create_text(x+cw//2,y+ch_h+8,text=txt,fill=RED if ch.get("is_duplicate") else GOLD,font=("Segoe UI",7))
        else:
            c.create_text(WIDTH//2,250,text="🎰",font=("Segoe UI Emoji",45))
            c.create_text(WIDTH//2,320,text="Summon Heroes!",fill=WHITE,font=("Segoe UI",20,"bold"))
        # Buttons
        by=440 if not self.gacha_results or len(self.gacha_results)<=5 else 430
        self.add_btn(60,by,180,45,f"🎲 x1 ({cost}g)",PURPLE,font_size=12,command=lambda:self._do_gacha(1))
        self.add_btn(260,by,210,45,f"🎲 x10 ({cost*10}g)",PURPLE,font_size=12,command=lambda:self._do_gacha(10))
        self.add_btn(490,by,160,45,"← Back",GRAY,font_size=12,command=self.goto_hub)

    def _set_gacha(self, mode): self.gacha_mode=mode; self.gacha_results=[]; self.draw_gacha()

    def _do_gacha(self, count):
        is_hi = self.gacha_mode=="high"; cost=(HIGH_COST if is_hi else NORMAL_COST)*count
        if self.gold < cost:
            self.gacha_results=[]; self.draw_gacha()
            self.canvas.create_text(WIDTH//2,400,text="Not enough gold!",fill=RED,font=("Segoe UI",14,"bold")); return
        self.gold -= cost; self.gacha_results=[]
        roll_fn = roll_high if is_hi else roll_normal
        for _ in range(count):
            ch = roll_fn()
            if any(existing["name"] == ch["name"] for existing in self.owned_chars):
                ch["is_duplicate"] = True
                self.shards[ch["name"]] = self.shards.get(ch["name"], 0) + 1
            else:
                self.owned_chars.append(ch)
            self.gacha_results.append(ch)
        self.do_save(); self.draw_gacha()

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
            sorted_owned = sorted(self.owned_chars, key=lambda c: (-c.get("stars", 1), self.owned_chars.index(c)))
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
    def goto_backpack(self): self.state="backpack"; self.bp_selected_char=None; self.bp_tab="loot"; self.draw_backpack()
    def _set_bp_tab(self, tab): self.bp_tab = tab; self.draw_backpack()
    def draw_backpack(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text="🎒 Backpack & Level Up",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        # Draw Tabs
        t_loot_c = ACCENT if getattr(self, 'bp_tab', 'loot') == "loot" else "#333"
        t_armr_c = ACCENT if getattr(self, 'bp_tab', 'loot') == "armor" else "#333"
        self.add_btn(20, 70, 150, 32, "Loot Items", t_loot_c, font_size=11, command=lambda: self._set_bp_tab("loot"))
        self.add_btn(180, 70, 150, 32, "Armory", t_armr_c, font_size=11, command=lambda: self._set_bp_tab("armor"))

        def it_sort(k):
            it=ITEMS[k]; t=it["type"]; name=it["name"]
            # Extract tier from key if it ends in _N
            tier=0
            if "_" in k:
                try: tier=int(k.split("_")[-1])
                except: pass
            return (t, name, tier)
        
        items_list = sorted([(k,v) for k,v in self.backpack.items() if v>0], key=lambda x: it_sort(x[0]))
        if getattr(self, 'bp_tab', 'loot') == "loot":
            items_list = [(k,v) for k,v in items_list if ITEMS[k]["type"] != "armor"]
        else:
            items_list = [(k,v) for k,v in items_list if ITEMS[k]["type"] == "armor"]

        if not items_list: c.create_text(30,120,text="Empty — win stages for loot!",fill="#888",font=("Segoe UI",11),anchor="w")
        iy=115
        for key,qty in items_list:
            it=ITEMS[key]
            c.create_rectangle(20,iy,380,iy+38,fill=BG_CARD,outline=it["color"],width=1)
            c.create_text(35,iy+19,text=f"{it['icon']} {it['name']} x{qty}",fill=WHITE,font=("Segoe UI",10),anchor="w")
            c.create_text(370,iy+19,text=it["desc"],fill=it["color"],font=("Segoe UI",8),anchor="e")
            if self.bp_selected_char is not None:
                if it["type"]=="exp": self.add_btn(385,iy+4,55,30,"Use",GREEN,font_size=8,command=lambda k=key:self.use_item(k))
                elif it["type"]=="buff": self.add_btn(385,iy+4,55,30,"Use",BLUE,font_size=8,command=lambda k=key:self.use_buff(k))
                elif it["type"]=="armor": self.add_btn(385,iy+4,55,30,"Equip",GOLD,font_size=8,command=lambda k=key:self.equip_armor(k))
            iy+=44
        c.create_text(500,80,text="Select Character:",fill=WHITE,font=("Segoe UI",13,"bold"),anchor="w")
        cy=105
        sorted_owned = sorted(self.owned_chars, key=lambda c: (c not in self.party, self.owned_chars.index(c)))
        for i,ch in enumerate(sorted_owned):
            if i>=8: break
            actual_idx = self.owned_chars.index(ch)
            sel=(self.bp_selected_char==actual_idx)
            c.create_rectangle(490,cy,870,cy+48,fill=BG_CARD if not sel else "#2a2a4e",outline=GOLD if sel else "#333",width=2 if sel else 1)
            ac = len(ch.get("armors_equipped", [])) + ch.get("armor_count", 0)
            c.create_text(510,cy+14,text=f"{ch['icon']} {ch['name']} {ch.get('rarity','★')} (Armor: {ac}/4)",fill=WHITE,font=("Segoe UI",9,"bold"),anchor="w")
            lvl=ch.get("level",1); exp=ch.get("exp",0); needed=exp_for_level(lvl+1) if lvl<MAX_LEVEL else 0
            c.create_text(510,cy+34,text=f"Lv.{lvl} EXP:{exp}/{needed} HP:{ch['hp']} ATK:{ch['atk']}",fill="#aaa",font=("Segoe UI",7),anchor="w")
            if lvl<MAX_LEVEL: draw_bar(c,790,cy+10,70,10,exp/needed if needed else 1,CYAN,"#222")
            else: c.create_text(830,cy+15,text="MAX",fill=GOLD,font=("Segoe UI",8,"bold"))
            if sel and ac > 0:
                self.add_btn(770,cy+24,60,20,"Unequip",RED,font_size=7,command=lambda idx=actual_idx:self.unequip_armor(idx))
            self.add_btn(848,cy+24,20,20,"→",ACCENT2,font_size=7,command=lambda idx=actual_idx:self.bp_select(idx))
            cy+=54
        self.add_btn(WIDTH//2-80,HEIGHT-50,160,38,"← Back",GRAY,font_size=11,command=self.goto_hub)

    def bp_select(self,idx): self.bp_selected_char=idx; self.draw_backpack()
    def use_item(self,key):
        if self.bp_selected_char is None or self.backpack.get(key,0)<=0: return
        ch=self.owned_chars[self.bp_selected_char]
        if ch.get("level",1)>=MAX_LEVEL: self.draw_backpack(); return
        it=ITEMS[key]
        
        from tkinter import simpledialog
        max_q = self.backpack[key]
        qty = simpledialog.askinteger("Quantity", f"Use how many {it['name']}?\n(Available: {max_q})", 
                                       parent=self.root, minvalue=1, maxvalue=max_q)
        if not qty: return
        
        self.backpack[key] -= qty
        buffs = self.calc_rune_buffs()
        total_exp = int(it["value"] * qty * (1 + buffs.get("exp", 0)))
        from game.constants import add_exp
        gained = add_exp(ch, total_exp)
        self.do_save(); self.draw_backpack()
        msg=f"+{total_exp} EXP"
        if gained>0: msg+=f" — LEVEL UP! (+{gained})"
        self.canvas.create_text(WIDTH//2,HEIGHT-80,text=msg,fill=GOLD,font=("Segoe UI",14,"bold"))

    def use_buff(self,key):
        if self.bp_selected_char is None or self.backpack.get(key,0)<=0: return
        ch=self.owned_chars[self.bp_selected_char]; cid=id(ch)
        if cid not in self.active_buffs: self.active_buffs[cid]=[]
        self.active_buffs[cid].append(key); self.backpack[key]-=1; self.do_save(); self.draw_backpack()
        self.canvas.create_text(WIDTH//2,HEIGHT-80,text="Buff applied for next fight!",fill=CYAN,font=("Segoe UI",13,"bold"))

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
            val = int(ITEMS[key]["value"] * 100)
            self.canvas.create_text(WIDTH//2,HEIGHT-80,text=f"{ITEMS[key]['name']} Equipped! +{val}% Stats",fill=GOLD,font=("Segoe UI",14, "bold"))

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

    # ── RUNES ──
    def goto_runes(self): self.state="runes"; self.draw_runes()
    def draw_runes(self):
        self.clear(); c=self.canvas
        # Rune Background
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill="#0a001a",outline="")
        c.create_text(20,30,text="🌟 Global Rune System",fill=GOLD,font=("Segoe UI",18,"bold"),anchor="w")
        
        # Current Buffs
        b = self.calc_rune_buffs()
        btxt = f"Stats: HP+{int(b['hp']*100)}% ATK+{int(b['atk']*100)}% DEF+{int(b['def']*100)}% SPD+{int(b['spd']*100)}%"
        etxt = f"Utility: Gold+{int(b['gold']*100)}% EXP+{int(b['exp']*100)}%"
        c.create_text(WIDTH//2, 75, text=btxt, fill=CYAN, font=("Segoe UI", 10, "bold"))
        c.create_text(WIDTH//2, 95, text=etxt, fill=GOLD, font=("Segoe UI", 10, "bold"))
        
        # Slots
        for i in range(3):
            rx = 50; ry = 120 + i*110
            c.create_rectangle(rx, ry, WIDTH-50, ry+90, fill="#16162a", outline=GOLD, width=2)
            c.create_text(rx+20, ry+25, text=f"Slot {i+1}", fill="#888", font=("Segoe UI", 10), anchor="w")
            
            rune_key = self.runes_equipped[i]
            if rune_key:
                it = ITEMS[rune_key]
                c.create_text(rx+20, ry+55, text=f"{it['icon']} {it['name']}", fill=WHITE, font=("Segoe UI", 14, "bold"), anchor="w")
                c.create_text(rx+220, ry+55, text=it["desc"], fill=it["color"], font=("Segoe UI", 11), anchor="w")
                self.add_btn(WIDTH-150, ry+30, 80, 35, "UNEQUIP", RED, font_size=9, command=lambda idx=i: self.unequip_rune(idx))
            else:
                c.create_text(rx+20, ry+55, text="Empty Slot", fill="#444", font=("Segoe UI", 14, "italic"), anchor="w")
                self.add_btn(WIDTH-150, ry+30, 80, 35, "EQUIP", GREEN, font_size=9, command=lambda idx=i: self.show_rune_inventory(idx))
                
        self.add_btn(WIDTH//2-80, HEIGHT-50, 160, 38, "← Back", GRAY, font_size=11, command=self.goto_hub)

    def calc_rune_buffs(self):
        b = {"hp":0.0, "atk":0.0, "def":0.0, "spd":0.0, "gold":0.0, "exp":0.0}
        for rk in self.runes_equipped:
            if rk:
                it = ITEMS[rk]
                if "atk" in rk: b["atk"] += it["value"]
                elif "hp" in rk: b["hp"] += it["value"]
                elif "def" in rk: b["def"] += it["value"]
                elif "spd" in rk: b["spd"] += it["value"]
                elif "gold" in rk: b["gold"] += it["value"]
                elif "exp" in rk: b["exp"] += it["value"]
        return b

    def unequip_rune(self, idx):
        rk = self.runes_equipped[idx]
        if rk:
            self.backpack[rk] = self.backpack.get(rk, 0) + 1
            self.runes_equipped[idx] = None
            self.refresh_all_stats(); self.do_save(); self.draw_runes()

    def show_rune_inventory(self, slot_idx):
        self.state = "rune_inv"; self.active_rune_slot = slot_idx
        self.draw_rune_inventory()

    def draw_rune_inventory(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text=f"Select Rune for Slot {self.active_rune_slot+1}",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        
        runes = [k for k,v in self.backpack.items() if v>0 and ITEMS[k]["type"]=="rune"]
        if not runes:
            c.create_text(WIDTH//2, HEIGHT//2, text="No Runes in Backpack", fill="#888", font=("Segoe UI", 14))
        else:
            iy = 80
            for rk in runes:
                it = ITEMS[rk]
                c.create_rectangle(50, iy, WIDTH-50, iy+50, fill=BG_CARD, outline=it["color"])
                c.create_text(70, iy+25, text=f"{it['icon']} {it['name']} (x{self.backpack[rk]})", fill=WHITE, font=("Segoe UI", 11), anchor="w")
                c.create_text(WIDTH-250, iy+25, text=it["desc"], fill=it["color"], font=("Segoe UI", 9), anchor="e")
                self.add_btn(WIDTH-150, iy+10, 80, 30, "SELECT", GREEN, font_size=9, command=lambda k=rk: self.equip_rune(k))
                iy += 55
                
        self.add_btn(WIDTH//2-80, HEIGHT-50, 160, 38, "← Cancel", GRAY, font_size=11, command=self.goto_runes)

    def equip_rune(self, rk):
        self.backpack[rk] -= 1
        self.runes_equipped[self.active_rune_slot] = rk
        self.refresh_all_stats(); self.do_save(); self.goto_runes()

    def refresh_all_stats(self):
        buffs = self.calc_rune_buffs()
        from game.constants import update_char_stats
        for ch in self.owned_chars:
            update_char_stats(ch, global_buffs=buffs)

    # ── STAGES ──
    def goto_stages(self): self.state="stages"; self.stage_page=self.max_stage_cleared // 4; self.draw_stages()
    def draw_stages(self):
        self.clear(); c=self.canvas
        c.create_rectangle(0,0,WIDTH,60,fill=BG_PANEL,outline="")
        c.create_text(20,30,text=f"⚔️ Stages (Cleared: {self.max_stage_cleared})",fill=WHITE,font=("Segoe UI",16,"bold"),anchor="w")
        self.add_btn(WIDTH-40, 15, 30, 30, "⛶", "#444", font_size=14, command=self.toggle_fullscreen)
        c.create_text(WIDTH-60,30,text=f"Page {self.stage_page+1}  🎟️ {self.backpack.get('skip_ticket', 0)}",fill="#aaa",font=("Segoe UI",12),anchor="e")
        
        if getattr(self, "notif_msg", None):
            c.create_rectangle(WIDTH//2-250, HEIGHT-110, WIDTH//2+250, HEIGHT-60, fill="#1a1a2e", outline=GOLD, width=2)
            c.create_text(WIDTH//2, HEIGHT-85, text=self.notif_msg, fill=GOLD, font=("Segoe UI", 11, "bold"), width=480)
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
                c.create_text(110,y+50,text=f"Enemies: {len(stg['enemies'])} | Reward: {(i+1)*150}g + Loot",fill="#aaa",font=("Segoe UI",10),anchor="w")
                if i>=len(FIXED_STAGES):
                    c.create_text(110,y+72,text="∞ Infinite Stage",fill=CYAN,font=("Segoe UI",9),anchor="w")
                
                # Button positions adjusted for better centering/balance
                self.add_btn(WIDTH-200,y+30,100,40,"FIGHT!",col,font_size=13,command=lambda idx=i:self.start_battle(idx))
                if i < self.max_stage_cleared:
                    self.add_btn(WIDTH-310,y+30,100,40,"🎟️ SKIP",PURPLE,font_size=11,command=lambda idx=i:self.use_skip_ticket(idx))
        if self.stage_page>0:
            self.add_btn(WIDTH//2-170,HEIGHT-50,100,38,"← Prev",ACCENT2,font_size=11,command=lambda:self._sp(-1))
        self.add_btn(WIDTH//2-40,HEIGHT-50,80,38,"← Hub",GRAY,font_size=10,command=self.goto_hub)
        if start+4 <= self.max_stage_cleared+1:
            self.add_btn(WIDTH//2+70,HEIGHT-50,100,38,"Next →",ACCENT2,font_size=11,command=lambda:self._sp(1))

    def _sp(self,d): self.stage_page=max(0,self.stage_page+d); self.draw_stages()

    def use_skip_ticket(self, idx):
        if self.backpack.get("skip_ticket", 0) <= 0:
            self.draw_stages()
            self.canvas.create_text(WIDTH//2, HEIGHT-80, text="No Skip Tickets left!", fill=RED, font=("Segoe UI", 14, "bold"))
            return
        self.backpack["skip_ticket"] -= 1
        reward = (idx+1)*150; self.gold += reward
        loot = roll_loot(idx, include_ticket=False)
        from collections import Counter
        loot_counts = Counter(loot)
        for k in loot:
            if ITEMS[k]["type"]=="gold": self.gold += ITEMS[k]["value"]
            else: self.backpack[k] = self.backpack.get(k, 0) + 1
        self.do_save(); self.draw_backpack()
        
        loot_str = ", ".join([f"{count}x {ITEMS[k]['icon']}" for k, count in loot_counts.items()])
        self.notif_msg = f"Skipped Stage {idx+1}! +{reward}g" + (f" and Loot: {loot_str}" if loot_str else "")
        self.notif_timer = 60 # ~3 seconds at 20fps

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
                col = i%2; row = i//2
                x = 20 + col*430; y = 80 + row*100
                c.create_rectangle(x, y, x+410, y+90, fill=BG_CARD, outline="#333")
                c.create_oval(x+10, y+15, x+70, y+75, fill=ch.get("color", ACCENT), outline="")
                c.create_text(x+40, y+45, text=ch.get("icon", "?"), font=("Segoe UI Emoji", 24))
                
                asc = ch.get("ascension", 0)
                req = 3 ** asc
                av = self.shards.get(ch["name"], 0)
                
                c.create_text(x+85, y+20, text=f"{ch['name']} {ch.get('rarity','★')} (Ascension {asc})", fill=WHITE, font=("Segoe UI", 12, "bold"), anchor="w")
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
