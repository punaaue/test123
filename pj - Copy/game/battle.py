import random, copy, time, math
from game.constants import *
from game.ui import Button, draw_bar

class BattleMixin:
    def start_battle(self, stage_idx):
        self.state = "battle"; self.stage_idx = stage_idx
        self.stage_page = stage_idx // 4
        self.current_stage = get_stage(stage_idx)
        self.b_enemies = [dict(e, max_hp=e["hp"]) for e in copy.deepcopy(self.current_stage["enemies"])]
        for i, e in enumerate(self.b_enemies):
            e["spd"] = int(10 * (1.01 ** stage_idx))
            e["is_player"] = False; e["b_idx"] = i
            
        self.b_party = []
        for i, ch in enumerate(self.party):
            # Create a clean copy for battle
            d = copy.deepcopy(ch)
            d["max_hp"] = d.get("hp", 100)
            d["cur_hp"] = d["max_hp"]
            d["is_player"] = True
            d["b_idx"] = i
            d["spd"] = d.get("spd", 10)
            self.b_party.append(d)
            
        self.b_log=[f"Battle Start! {len(self.b_party)} heroes ready."]; self.b_enemy_idx=0
        self.round_damage = 0
        self.b_particles = []
        self.b_state = "normal"
        self.b_shake = 0
        self.b_flash = None
        self.build_turn_queue()
        self.next_turn()

    def build_turn_queue(self):
        self.turn_queue = []
        for c in self.b_party:
            if c["cur_hp"] > 0: self.turn_queue.append(c)
        for e in self.b_enemies:
            if e["hp"] > 0: self.turn_queue.append(e)
        self.turn_queue.sort(key=lambda x: x.get("spd", 10), reverse=True)

    def next_turn(self):
        if not hasattr(self, "round_damage"): self.round_damage = 0
        if all(e["hp"]<=0 for e in self.b_enemies):
            if self.state != "battle": return
            self.state = "victory_processing"

            reward=(self.stage_idx+1)*150; self.gold+=reward
            loot=roll_loot(self.stage_idx)
            for k in loot:
                if ITEMS[k]["type"]=="gold": self.gold+=ITEMS[k]["value"]
                else: self.backpack[k]=self.backpack.get(k,0)+1
            if self.stage_idx >= self.max_stage_cleared: self.max_stage_cleared = self.stage_idx + 1
            self.victory_reward=reward; self.victory_loot=loot
            self.state="victory"; self.do_save(); self.draw_victory(); return
            
        if all(c["cur_hp"]<=0 for c in self.b_party):
            self.state="defeat"; self.draw_defeat(); return

        while self.turn_queue:
            actor = self.turn_queue.pop(0)
            if actor["is_player"] and self.b_party[actor["b_idx"]]["cur_hp"] > 0:
                self.b_turn = "player"
                self.b_selected_char = actor["b_idx"]
                self.draw_battle()
                return
            elif not actor["is_player"] and self.b_enemies[actor["b_idx"]]["hp"] > 0:
                self.b_turn = "enemy"
                self.b_active_enemy = actor["b_idx"]
                self.draw_battle()
                self.root.after(200, self.enemy_turn)
                return
                
        self.round_damage = 0
        self.build_turn_queue()
        self.next_turn()

    def _find_orig(self, ch):
        for c in self.party:
            if c["name"]==ch["name"] and c.get("level")==ch.get("level"): return c
        return ch

    def draw_battle(self):
        self.clear(); c=self.canvas
        
        # Biome Background
        stg_name = self.current_stage.get("name", "")
        bg_col = "#000b1a" # Default deep space
        if "Volcano" in stg_name or "Inferno" in stg_name: bg_col = "#1a0500"
        elif "Forest" in stg_name or "Swamp" in stg_name: bg_col = "#051000"
        elif "Cave" in stg_name or "Depths" in stg_name: bg_col = "#0a0a0a"
        elif "Sky" in stg_name or "Celestial" in stg_name: bg_col = "#001a1a"
        elif "Shadow" in stg_name or "Nightmare" in stg_name: bg_col = "#0a001a"
        
        # Screen Shake Offset
        off_x, off_y = 0, 0
        if getattr(self, "b_shake", 0) > 0:
            off_x = random.randint(-self.b_shake, self.b_shake)
            off_y = random.randint(-self.b_shake, self.b_shake)
            
        c.create_rectangle(0,0,WIDTH,HEIGHT,fill=bg_col,outline="")
        
        # Hit Flash
        if getattr(self, "b_flash", None):
            c.create_rectangle(0,0,WIDTH,HEIGHT,fill=self.b_flash,stipple="gray50")

        c.create_rectangle(0,0,WIDTH,50,fill=BG_PANEL,outline="")
        c.create_text(WIDTH//2 + off_x,25 + off_y,text=f"⚔️ {self.current_stage.get('name', 'Battle')}",fill=WHITE,font=("Segoe UI",16,"bold"))
        # Turn order UI and Damage
        if hasattr(self, "turn_queue"):
            c.create_text(WIDTH//2 + off_x, 60 + off_y, text=f"📊 Round Damage: {getattr(self, 'round_damage', 0)}", fill=GOLD, font=("Segoe UI", 11, "bold"))
            
            # Combine active + queue with safety checks
            b_turn = getattr(self, "b_turn", None)
            if b_turn == "player":
                active = [self.b_party[self.b_selected_char]] if self.b_selected_char < len(self.b_party) else []
            elif b_turn == "enemy":
                idx = getattr(self, "b_active_enemy", 0)
                active = [self.b_enemies[idx]] if idx < len(self.b_enemies) else []
            else:
                active = []
                
            display_q = active + self.turn_queue
            
            qx = WIDTH//2 - (len(display_q[:12])*35)//2
            for i, actor in enumerate(display_q[:12]):
                frame_color = BLUE if actor.get("is_player") else RED
                c.create_rectangle(qx+i*35, 70, qx+i*35+30, 100, fill=BG_CARD, outline=frame_color, width=3 if i==0 else 1)
                c.create_text(qx+i*35+15, 85, text=actor.get("icon", "?"), font=("Segoe UI Emoji", 14))
                if i==0:
                    c.create_text(qx+i*35+15, 108, text="ACT", fill=frame_color, font=("Segoe UI", 8, "bold"))
                    
        ew=140; ex=(WIDTH-len(self.b_enemies)*(ew+10))//2
        for i,en in enumerate(self.b_enemies):
            x=ex+i*(ew+10); y=125; alive=en["hp"]>0
            c.create_rectangle(x,y,x+ew,y+120,fill=BG_CARD if alive else "#1a1a1a",outline=en["color"] if alive else "#333",width=2)
            c.create_text(x+ew//2,y+25,text=en["icon"],font=("Segoe UI Emoji",20))
            c.create_text(x+ew//2,y+55,text=en["name"],fill=WHITE if alive else "#555",font=("Segoe UI",10,"bold"))
            if alive:
                draw_bar(c,x+10,y+75,ew-20,12,en["hp"]/en["max_hp"],RED)
                c.create_text(x+ew//2,y+100,text=f"HP:{en['hp']}/{en['max_hp']}",fill="#aaa",font=("Segoe UI",8))
                if self.b_turn=="player":
                    sl="▶" if i==self.b_enemy_idx else "Target"; cl=GOLD if i==self.b_enemy_idx else ACCENT
                    self.add_btn(x+10,y+105,ew-20,16,sl,cl,font_size=7,command=lambda idx=i:self.set_target(idx))
            else: c.create_text(x+ew//2,y+90,text="DEFEATED",fill=RED,font=("Segoe UI",9,"bold"))
        pw=160; px=(WIDTH-len(self.b_party)*(pw+10))//2
        for i,ch in enumerate(self.b_party):
            x=px+i*(pw+10); y=310; alive=ch["cur_hp"]>0
            sel=(i==self.b_selected_char and self.b_turn=="player")
            ol=GOLD if sel else (ch["color"] if alive else "#333")
            c.create_rectangle(x,y,x+pw,y+130,fill=BG_CARD if alive else "#1a1a1a",outline=ol,width=2 if sel else 1)
            c.create_text(x+pw//2,y+18,text=ch["icon"],font=("Segoe UI Emoji",14))
            c.create_text(x+pw//2,y+40,text=f"{ch['name']} Lv.{ch.get('level',1)}",fill=WHITE if alive else "#555",font=("Segoe UI",10,"bold"))
            draw_bar(c,x+10,y+58,pw-20,14,ch["cur_hp"]/ch["max_hp"],GREEN)
            c.create_text(x+pw//2,y+85,text=f"HP:{ch['cur_hp']}/{ch['max_hp']}",fill="#aaa",font=("Segoe UI",9))
            c.create_text(x+10,y+100,text=f"ATK:{ch['atk']} DEF:{ch['def']}",fill="#888",font=("Segoe UI",7),anchor="w")
            if alive and getattr(self, "b_state", "normal") == "selecting_heal_target":
                self.add_btn(x+5, y+108, pw-10, 18, "💚 HEAL", GREEN, font_size=8, command=lambda idx=i: self.execute_heal(idx))
        if getattr(self, "b_turn", None) == "player":
            char_idx = getattr(self, "b_selected_char", 0)
            if char_idx < len(self.b_party):
                act = self.b_party[char_idx]
                if act and act.get("cur_hp", 0) > 0:
                    atk_btn = self.add_btn(120,470,150,45,"⚔️ Attack",ACCENT,font_size=13,command=self.do_attack)
                    skill_btn = self.add_btn(300,470,180,45,f"✨ {act.get('skill','Skill')}",PURPLE,font_size=11,command=self.do_skill)
                    if getattr(skill_btn, "is_hover", False):
                        sd = act.get("skill_dmg", 1.5)
                        info = f"Heals ally for {int(act['atk']*2)} HP" if sd == 0 else f"Deals {int(act['atk']*sd)} base dmg"
                        c.create_rectangle(300, 425, 480, 455, fill="#2a2a4e", outline=PURPLE, width=1)
                        c.create_text(390, 440, text=info, fill=WHITE, font=("Segoe UI", 9))
                    if getattr(atk_btn, "is_hover", False):
                        info = f"Deals ~{act['atk']-3} to {act['atk']+5} base dmg"
                        c.create_rectangle(120, 425, 270, 455, fill="#2a2a4e", outline=ACCENT, width=1)
                        c.create_text(195, 440, text=info, fill=WHITE, font=("Segoe UI", 9))
            self.add_btn(510,470,130,45,"🏃 Flee",GRAY,font_size=13,command=self.goto_hub)
        c.create_rectangle(0,540,WIDTH,HEIGHT,fill="#111122",outline="")
        c.create_text(WIDTH//2,570,text=" | ".join(self.b_log[-3:]),fill="#ccc",font=("Segoe UI",10),width=WIDTH-20)
        self._draw_particles()

    def _get_actor_coords(self, actor):
        # Floating idle animation
        float_off = math.sin(self.anim_frame * 0.2 + actor.get("b_idx", 0)) * 5
        if actor.get("is_player"):
            pw=160; px=(WIDTH-len(self.b_party)*(pw+10))//2
            i = actor["b_idx"]; x = px+i*(pw+10); y = 310 + float_off
            return (x + pw//2, y + 50)
        else:
            ew=140; ex=(WIDTH-len(self.b_enemies)*(ew+10))//2
            i = actor["b_idx"]; x = ex+i*(ew+10); y = 125 + float_off
            return (x + ew//2, y + 60)

    def _spawn_particles(self, x, y, color, icon):
        for _ in range(15):
            self.b_particles.append({
                "x": x, "y": y,
                "vx": random.uniform(-8, 8),
                "vy": random.uniform(-10, 5),
                "life": 1.0, "color": color, "icon": icon or "✨"
            })

    def _update_particles(self):
        for p in self.b_particles[:]:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            p["vy"] += 0.6; p["life"] -= 0.08
            if p["life"] <= 0: self.b_particles.remove(p)

    def _draw_particles(self):
        for p in getattr(self, "b_particles", []):
            sz = int(8 + p["life"] * 12)
            self.canvas.create_text(p["x"], p["y"], text=p["icon"], fill=p["color"], font=("Segoe UI Emoji", sz))

    def set_target(self,idx): self.b_enemy_idx=idx; self.draw_battle()

    def _find_target(self):
        t=self.b_enemies[self.b_enemy_idx]
        if t["hp"]<=0:
            for i,e in enumerate(self.b_enemies):
                if e["hp"]>0: self.b_enemy_idx=i; return e
        return t

    def do_attack(self):
        if self.b_turn != "player": return
        self.b_turn = "busy"
        a=self.b_party[self.b_selected_char]
        if a["cur_hp"]<=0: return
        t=self._find_target(); dmg=max(1,a["atk"]-t["def"]//2+random.randint(-3,5))
        t["hp"]=max(0,t["hp"]-dmg); self.b_log.append(f"{a['name']} hits {t['name']} for {dmg}!"); 
        self.round_damage += dmg
        tx, ty = self._get_actor_coords(t)
        self._spawn_particles(tx, ty, a["color"], a["icon"])
        self.b_shake = 10
        self.b_flash = "#330000" if t.get("is_player") else "#ffffff"
        self.draw_battle()
        self.after_action()

    def do_skill(self):
        if self.b_turn != "player": return
        a=self.b_party[self.b_selected_char]
        if a["cur_hp"]<=0: return
        sd=a.get("skill_dmg",1.5); sn=a.get("skill","Skill")
        
        # Double click detection for heal
        now = time.time()
        is_double = (now - getattr(self, "_last_skill_time", 0) < 0.3)
        self._last_skill_time = now
        
        if sd==0:
            if is_double:
                # Auto-heal lowest HP ally
                alive_allies = [c for c in self.b_party if c["cur_hp"] > 0]
                if alive_allies:
                    ht = min(alive_allies, key=lambda c: c["cur_hp"]/c["max_hp"])
                    self.execute_heal(self.b_party.index(ht))
                return
            self.b_state = "selecting_heal_target"
            self.draw_battle()
        else:
            self.b_turn = "busy"
            t=self._find_target(); dmg=max(1,int(a["atk"]*sd)-t["def"]//3+random.randint(-2,8))
            t["hp"]=max(0,t["hp"]-dmg); self.b_log.append(f"{a['name']} uses {sn} on {t['name']} for {dmg}!")
            self.round_damage += dmg
            tx, ty = self._get_actor_coords(t)
            self._spawn_particles(tx, ty, PURPLE, a["icon"])
            self.b_shake = 15
            self.b_flash = PURPLE
            self.draw_battle()
            self.after_action()

    def execute_heal(self, target_idx):
        if self.b_turn != "player": return
        self.b_turn = "busy"
        a = self.b_party[self.b_selected_char]
        ht = self.b_party[target_idx]
        heal = int(a["atk"]*2); ht["cur_hp"] = min(ht["max_hp"], ht["cur_hp"]+heal)
        self.b_log.append(f"{a['name']} heals {ht['name']} +{heal}!")
        tx, ty = self._get_actor_coords(ht)
        self._spawn_particles(tx, ty, GREEN, "✨")
        self.b_state = "normal"
        self.draw_battle()
        self.after_action()

    def after_action(self):
        def finish():
            self.next_turn()
        self.root.after(200, finish)

    def enemy_turn(self):
        # Use the actor index set by next_turn
        en = self.b_enemies[self.b_active_enemy]
        
        alive = [c for c in self.b_party if c["cur_hp"] > 0]
        if alive:
            t=random.choice(alive)
            dmg=max(1,en["atk"]-t["def"]//2+random.randint(-3,5))
            self.b_log.append(f"{en['name']} hits {t['name']} for {dmg}!")
            self.b_shake = 12; self.b_flash = "#ff0000"
                
            t["cur_hp"]=max(0,t["cur_hp"]-dmg)
            tx, ty = self._get_actor_coords(t)
            self._spawn_particles(tx, ty, RED, en["icon"])
            
        self.draw_battle()
        self.after_action()

    def draw_victory(self):
        self.clear(); c=self.canvas
        c.create_text(WIDTH//2,70,text="🏆",font=("Segoe UI Emoji",45))
        c.create_text(WIDTH//2,135,text="VICTORY!",fill=GOLD,font=("Segoe UI",34,"bold"))
        c.create_text(WIDTH//2,175,text=f"+{self.victory_reward} Gold",fill=GREEN,font=("Segoe UI",15))
        c.create_text(WIDTH//2,210,text="Loot Drops:",fill=WHITE,font=("Segoe UI",13,"bold"))
        y=235
        from collections import Counter
        loot_counts = Counter(self.victory_loot)
        for k, count in loot_counts.items():
            it=ITEMS[k]; c.create_text(WIDTH//2,y,text=f"{it['icon']} {it['name']} x{count} — {it['desc']}",fill=it["color"],font=("Segoe UI",11)); y+=22
        self.add_btn(WIDTH//2-150,y+15,90,45,"Hub",GRAY,command=self.goto_hub)
        self.add_btn(WIDTH//2-50,y+15,100,45,"Retry",BLUE,command=lambda:self.start_battle(self.stage_idx))
        self.add_btn(WIDTH//2+60,y+15,100,45,"Next ⚔️",GREEN,command=lambda:self.start_battle(self.stage_idx+1))

    def draw_defeat(self):
        self.clear(); c=self.canvas
        c.create_text(WIDTH//2,150,text="💀",font=("Segoe UI Emoji",50))
        c.create_text(WIDTH//2,250,text="DEFEATED",fill=RED,font=("Segoe UI",36,"bold"))
        self.add_btn(WIDTH//2-110,350,100,50,"Return",GRAY,command=self.goto_hub)
        self.add_btn(WIDTH//2+10,350,100,50,"Retry",BLUE,command=lambda:self.start_battle(self.stage_idx))
