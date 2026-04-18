import random, math, json, os, copy

WIDTH = 900
HEIGHT = 650

BG_DARK = "#0f0f1a"
BG_CARD = "#1a1a2e"
BG_PANEL = "#16213e"
ACCENT = "#e94560"
ACCENT2 = "#0f3460"
GOLD = "#f5c518"
WHITE = "#eaeaea"
GREEN = "#00e676"
RED = "#ff1744"
BLUE = "#448aff"
PURPLE = "#7c4dff"
CYAN = "#00e5ff"
GRAY = "#555555"
ORANGE = "#ff9100"
MAX_LEVEL = 999999
SAVE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "savegame.json")

class ItemDict(dict):
    def __getitem__(self, key):
        if key.startswith("boss_armor_"):
            tier = int(key.split("_")[2])
            val = 0.15 + (tier - 1) * 0.05
            return {"name": f"Boss Armor T{tier}", "desc": f"+{int(val*100)}% to all Stats", "value": val, "type": "armor", "icon": "🛡️", "color": "#ffb300"}
        if key.startswith("exp_potion_"):
            tier = int(key.split("_")[2])
            if tier == 1: val = 100; name = "EXP Potion I"
            elif tier == 2: val = 500; name = "EXP Potion II"
            elif tier == 3: val = 2000; name = "EXP Potion III"
            else: 
                val = int(2000 * (2.5 ** (tier - 3)))
                name = f"EXP Potion T{tier}"
            return {"name": name, "desc": f"Grants {val:,} EXP", "value": val, "type": "exp", "icon": "🧪", "color": "#66bb6a"}
            
        if key not in self:
            return {"name": "Unknown Item", "desc": "???", "value": 0, "type": "loot"}
        return super().__getitem__(key)

ITEMS = ItemDict({
    "buff_atk":     {"name": "ATK Boost",      "icon": "⚔️", "color": "#ef5350", "type": "buff", "stat": "atk", "value": 0.3, "desc": "+30% ATK 1 fight"},
    "buff_def":     {"name": "DEF Boost",      "icon": "🛡️", "color": "#5c6bc0", "type": "buff", "stat": "def", "value": 0.3, "desc": "+30% DEF 1 fight"},
    "buff_hp":      {"name": "HP Boost",       "icon": "❤️", "color": "#ec407a", "type": "buff", "stat": "hp",  "value": 0.3, "desc": "+30% HP 1 fight"},
    "gold_bag":     {"name": "Gold Bag",       "icon": "💰", "color": "#ffd740", "type": "gold", "value": 500,  "desc": "+500 Gold"},
    "boss_armor":   {"name": "Boss Armor",     "icon": "🛡️", "color": "#ffb300", "type": "armor", "value": 0.15, "desc": "+15% HP/DEF (Legacy)"},
    "skip_ticket":  {"name": "Skip Ticket",    "icon": "🎟️", "color": "#f06292", "type": "special", "value": 1,  "desc": "Instantly farm a cleared stage"},
    
    # Advanced Gear
    "weapon_1":     {"name": "Iron Sword",     "icon": "⚔️", "color": "#90a4ae", "type": "weapon", "value": 0.10, "desc": "+10% ATK"},
    "weapon_2":     {"name": "Steel Blade",    "icon": "⚔️", "color": "#607d8b", "type": "weapon", "value": 0.25, "desc": "+25% ATK"},
    "armor_1":      {"name": "Iron Plate",     "icon": "🛡️", "color": "#90a4ae", "type": "armor",  "value": 0.10, "desc": "+10% HP/DEF"},
    "armor_2":      {"name": "Steel Shell",    "icon": "🛡️", "color": "#607d8b", "type": "armor",  "value": 0.25, "desc": "+25% HP/DEF"},
    "acc_1":        {"name": "Speed Boots",    "icon": "👟", "color": "#81c784", "type": "accessory","value": 0.10, "desc": "+10% SPD"},
    "acc_2":        {"name": "Wind Ring",      "icon": "💍", "color": "#4fc3f7", "type": "accessory","value": 0.20, "desc": "+20% SPD"},
})

def get_stage_loot_table(stage_idx):
    tier_1 = max(1, (stage_idx // 10) + 1)
    tier_2 = tier_1 + 1
    
    table = [(f"exp_potion_{tier_1}", 0.80), (f"exp_potion_{tier_1}", 0.50), ("buff_atk", 0.30), ("buff_def", 0.25)]
    table += [(f"exp_potion_{tier_2}", 0.55), ("buff_hp", 0.30), ("gold_bag", 0.15)]
    
    if stage_idx >= 3:
        table += [(f"exp_potion_{tier_2}", 0.40)]
    if stage_idx >= 6:
        table += [("gold_bag", 0.30)]
    if stage_idx > 10:
        table += [("weapon_1", 0.15), ("armor_1", 0.15), ("acc_1", 0.10)]
    if stage_idx > 40:
        table += [("weapon_2", 0.08), ("armor_2", 0.08), ("acc_2", 0.05)]
    return table

def roll_loot(stage_idx, include_ticket=True):
    table = get_stage_loot_table(stage_idx)
    drops = []
    for key, chance in table:
        if random.random() < chance:
            drops.append(key)
    if not drops:
        tier_1 = max(1, (stage_idx // 10) + 1)
        drops.append(f"exp_potion_{tier_1}")
    if (stage_idx + 1) % 10 == 0:
        tier = (stage_idx + 1) // 10
        drops.append(f"boss_armor_{tier}")
    if include_ticket:
        drops.append("skip_ticket")
    return drops

def get_stage_gold_reward(stage_idx):
    return int(200 + stage_idx * 150 + (1.05 ** stage_idx) * 50)

def exp_for_level(level):
    return int(80 * (level ** 1.5))

def get_level_stats(base_char, level, armors=None, legacy_armor_count=0, ascension=0):
    s = 1.02 ** (level - 1)
    asc_mult = 1.2 ** ascension
    hp_m, atk_m, def_m, spd_m = 1.0, 1.0, 1.0, 1.0
    hp_m += (legacy_armor_count * 0.15); atk_m += (legacy_armor_count * 0.15)
    
    if armors:
        for a_key in armors:
            it = ITEMS[a_key]
            if it["type"] == "weapon": atk_m += it["value"]
            elif it["type"] == "armor": hp_m += it["value"]; def_m += it["value"]
            elif it["type"] == "accessory": spd_m += it["value"]; atk_m += it["value"]*0.3
            else: hp_m += it["value"]; atk_m += it["value"]

    b_hp = base_char.get("base_hp", base_char["hp"])
    b_atk = base_char.get("base_atk", base_char["atk"])
    b_def = base_char.get("base_def", base_char["def"])
    b_spd = base_char.get("base_spd", base_char.get("spd", 10))

    return {
        "hp": int(b_hp * s * hp_m * asc_mult),
        "atk": int(b_atk * s * atk_m * asc_mult),
        "def": int(b_def * s * def_m * asc_mult),
        "spd": int(b_spd * spd_m * s)
    }

def update_char_stats(ch):
    if "base_hp" not in ch:
        ch["base_hp"] = ch["hp"]; ch["base_atk"] = ch["atk"]; ch["base_def"] = ch["def"]; ch["base_spd"] = ch.get("spd", 10)
    stats = get_level_stats(ch, ch['level'], ch.get('armors_equipped'), ascension=ch.get('ascension', 0))
    ch.update(stats)

def make_new_char(template):
    ch = dict(template); ch["level"] = 1; ch["exp"] = 0; ch["armor_count"] = 0; ch["armors_equipped"] = []; ch["ascension"] = 0
    ch["base_hp"] = ch["hp"]; ch["base_atk"] = ch["atk"]; ch["base_def"] = ch["def"]; ch["base_spd"] = ch["spd"]
    return ch

def add_exp(char, amount):
    if char["level"] >= MAX_LEVEL: return 0
    char["exp"] += amount; gained = 0
    while char["level"] < MAX_LEVEL and char["exp"] >= exp_for_level(char["level"]+1):
        char["exp"] -= exp_for_level(char["level"]+1); char["level"] += 1; gained += 1
        update_char_stats(char)
    if char["level"] >= MAX_LEVEL: char["exp"] = 0
    return gained

# ── CHARACTERS ── (1★ to 12★)
ALL_CHARACTERS = [
    # 1★
    {"name":"Slime",        "hp":60, "atk":15,"def":5, "spd":6, "skill":"Bounce",       "skill_dmg":1.0,"color":"#76ff03","rarity":"★",       "icon":"🟢","stars":1},
    {"name":"Goblin",       "hp":70, "atk":20,"def":7, "spd":9, "skill":"Stab",          "skill_dmg":1.3,"color":"#aed581","rarity":"★",       "icon":"👺","stars":1},
    {"name":"Forest Bat",   "hp":45, "atk":18,"def":4, "spd":15,"skill":"Bite",          "skill_dmg":1.1,"color":"#7e57c2","rarity":"★",       "icon":"🦇","stars":1},
    {"name":"Cave Rat",     "hp":50, "atk":16,"def":5, "spd":12,"skill":"Scurry",        "skill_dmg":1.0,"color":"#9e9e9e","rarity":"★",       "icon":"🐭","stars":1},
    # 2★
    {"name":"Iron Golem",   "hp":180,"atk":25,"def":30,"spd":4, "skill":"Earth Wall",    "skill_dmg":1.2,"color":"#8d6e63","rarity":"★★",      "icon":"🛡️","stars":2},
    {"name":"Wolf Rider",   "hp":100,"atk":30,"def":10,"spd":14,"skill":"Charge",        "skill_dmg":1.5,"color":"#a1887f","rarity":"★★",      "icon":"🐺","stars":2},
    {"name":"Apprentice",   "hp":75, "atk":35,"def":8, "spd":11,"skill":"Magic Bolt",    "skill_dmg":1.6,"color":"#64b5f6","rarity":"★★",      "icon":"🧙","stars":2},
    {"name":"Wood Elf",     "hp":85, "atk":32,"def":9, "spd":13,"skill":"Leaf Blade",    "skill_dmg":1.4,"color":"#81c784","rarity":"★★",      "icon":"🧝","stars":2},
    # 3★
    {"name":"Blaze Knight", "hp":120,"atk":35,"def":15,"spd":10,"skill":"Flame Slash",   "skill_dmg":1.8,"color":"#ff6b35","rarity":"★★★",     "icon":"🔥","stars":3},
    {"name":"Frost Mage",   "hp":90, "atk":45,"def":10,"spd":12,"skill":"Ice Storm",     "skill_dmg":2.0,"color":"#4fc3f7","rarity":"★★★",     "icon":"❄️","stars":3},
    {"name":"Shadow Rogue", "hp":85, "atk":40,"def":8, "spd":18,"skill":"Shadow Strike", "skill_dmg":2.2,"color":"#7c4dff","rarity":"★★★",     "icon":"🗡️","stars":3},
    {"name":"Holy Priest",  "hp":100,"atk":20,"def":12,"spd":8, "skill":"Divine Heal",   "skill_dmg":0,  "color":"#ffd740","rarity":"★★★",     "icon":"✨","stars":3},
    {"name":"Wind Archer",  "hp":80, "atk":42,"def":9, "spd":16,"skill":"Gale Arrow",    "skill_dmg":1.9,"color":"#69f0ae","rarity":"★★★",     "icon":"🏹","stars":3},
    {"name":"Stone Monk",   "hp":150,"atk":25,"def":25,"spd":7, "skill":"Iron Fist",     "skill_dmg":1.7,"color":"#ffb74d","rarity":"★★★",     "icon":"🧘","stars":3},
    # 4★
    {"name":"Dark Lord",    "hp":150,"atk":50,"def":20,"spd":14,"skill":"Void Blast",    "skill_dmg":2.5,"color":"#e040fb","rarity":"★★★★",    "icon":"👿","stars":4},
    {"name":"Thunder God",  "hp":130,"atk":55,"def":18,"spd":15,"skill":"Lightning",     "skill_dmg":2.4,"color":"#ffee58","rarity":"★★★★",    "icon":"⚡","stars":4},
    {"name":"Paladin",      "hp":200,"atk":40,"def":35,"spd":8, "skill":"Holy Shield",   "skill_dmg":0,  "color":"#fff176","rarity":"★★★★",    "icon":"🛡️","stars":4},
    {"name":"Assasin",      "hp":110,"atk":60,"def":12,"spd":22,"skill":"Assasinate",    "skill_dmg":2.8,"color":"#212121","rarity":"★★★★",    "icon":"👤","stars":4},
    {"name":"Lava Golem",   "hp":250,"atk":45,"def":25,"spd":5, "skill":"Magma Slam",    "skill_dmg":2.2,"color":"#bf360c","rarity":"★★★★",    "icon":"🌋","stars":4},
    # 5★
    {"name":"Phoenix",      "hp":180,"atk":65,"def":22,"spd":18,"skill":"Rebirth Flame", "skill_dmg":2.8,"color":"#ff5722","rarity":"★★★★★",   "icon":"🔥","stars":5},
    {"name":"Archangel",    "hp":220,"atk":55,"def":30,"spd":16,"skill":"Holy Wrath",    "skill_dmg":2.6,"color":"#e1f5fe","rarity":"★★★★★",   "icon":"👼","stars":5},
    {"name":"Nature Spirit","hp":190,"atk":45,"def":25,"spd":20,"skill":"Forest Bloom",  "skill_dmg":0,  "color":"#4caf50","rarity":"★★★★★",   "icon":"🍃","stars":5},
    {"name":"Sea Kraken",   "hp":250,"atk":70,"def":28,"spd":12,"skill":"Tidal Wave",    "skill_dmg":2.7,"color":"#0277bd","rarity":"★★★★★",   "icon":"🐙","stars":5},
    {"name":"Griffin",      "hp":200,"atk":60,"def":20,"spd":25,"skill":"Sky Claw",      "skill_dmg":2.5,"color":"#fb8c00","rarity":"★★★★★",   "icon":"🦅","stars":5},
    # 6★
    {"name":"Dragon King",  "hp":300,"atk":80,"def":40,"spd":20,"skill":"Dragon Fury",   "skill_dmg":3.0,"color":"#d50000","rarity":"★★★★★★",  "icon":"🐉","stars":6},
    {"name":"Death Knight", "hp":280,"atk":85,"def":35,"spd":17,"skill":"Soul Reap",     "skill_dmg":3.2,"color":"#4a148c","rarity":"★★★★★★",  "icon":"💀","stars":6},
    {"name":"Moon Goddess", "hp":260,"atk":75,"def":45,"spd":18,"skill":"Lunar Heal",    "skill_dmg":0,  "color":"#9575cd","rarity":"★★★★★★",  "icon":"🌙","stars":6},
    {"name":"War Machine",  "hp":350,"atk":90,"def":50,"spd":10,"skill":"Laser Beam",    "skill_dmg":3.1,"color":"#607d8b","rarity":"★★★★★★",  "icon":"🤖","stars":6},
    {"name":"Valkyrie",     "hp":290,"atk":95,"def":38,"spd":24,"skill":"Valhalla Call", "skill_dmg":3.3,"color":"#f48fb1","rarity":"★★★★★★",  "icon":"⚔️","stars":6},
    # 7★
    {"name":"Celestial",    "hp":400,"atk":100,"def":50,"spd":22,"skill":"Star Fall",    "skill_dmg":3.5,"color":"#00bcd4","rarity":"★★★★★★★", "icon":"🌟","stars":7},
    {"name":"Demon Emperor","hp":380,"atk":110,"def":45,"spd":20,"skill":"Hell Storm",   "skill_dmg":3.8,"color":"#880e4f","rarity":"★★★★★★★", "icon":"😈","stars":7},
    {"name":"Solar Priestess","hp":320,"atk":120,"def":40,"spd":24,"skill":"Sun Grace",   "skill_dmg":0,  "color":"#ffeb3b","rarity":"★★★★★★★", "icon":"☀️","stars":7},
    {"name":"Abyss Watcher","hp":420,"atk":115,"def":55,"spd":26,"skill":"Void Slash",   "skill_dmg":3.6,"color":"#311b92","rarity":"★★★★★★★", "icon":"👁️","stars":7},
    {"name":"Behemoth",     "hp":600,"atk":90, "def":70,"spd":12,"skill":"Earthquake",   "skill_dmg":3.4,"color":"#795548","rarity":"★★★★★★★", "icon":"🐗","stars":7},
    # 8★
    {"name":"Titan",        "hp":550,"atk":130,"def":65,"spd":18,"skill":"World Crush",  "skill_dmg":4.0,"color":"#ff6f00","rarity":"★"*8,     "icon":"🗿","stars":8},
    {"name":"Void Walker",  "hp":450,"atk":150,"def":50,"spd":28,"skill":"Void Rift",    "skill_dmg":4.2,"color":"#311b92","rarity":"★"*8,     "icon":"🌀","stars":8},
    {"name":"Eternal Sage", "hp":500,"atk":100,"def":60,"spd":30,"skill":"Ancient Wisdom","skill_dmg":0, "color":"#9c27b0","rarity":"★"*8,     "icon":"🔮","stars":8},
    {"name":"Ghost Samurai","hp":480,"atk":160,"def":45,"spd":32,"skill":"Ghost Blade",   "skill_dmg":4.5,"color":"#cfd8dc","rarity":"★"*8,     "icon":"👺","stars":8},
    {"name":"Berserker King","hp":460,"atk":180,"def":40,"spd":22,"skill":"Rage",        "skill_dmg":4.8,"color":"#d32f2f","rarity":"★"*8,     "icon":"👺","stars":8},
    # 9★
    {"name":"Cosmic Dragon","hp":700,"atk":180,"def":80,"spd":25,"skill":"Nova Blast",   "skill_dmg":4.5,"color":"#aa00ff","rarity":"★"*9,     "icon":"🌌","stars":9},
    {"name":"Time Lord",    "hp":600,"atk":200,"def":70,"spd":35,"skill":"Time Warp",    "skill_dmg":5.0,"color":"#00e5ff","rarity":"★"*9,     "icon":"⏳","stars":9},
    {"name":"Cosmic Caretaker","hp":650,"atk":150,"def":75,"spd":32,"skill":"Universal Heal","skill_dmg":0,"color":"#26a69a","rarity":"★"*9,     "icon":"🌍","stars":9},
    {"name":"Nebula Queen", "hp":550,"atk":220,"def":65,"spd":40,"skill":"Nebula Burst",  "skill_dmg":5.2,"color":"#e91e63","rarity":"★"*9,     "icon":"☄️","stars":9},
    {"name":"Star Eater",   "hp":750,"atk":210,"def":85,"spd":28,"skill":"Singularity",  "skill_dmg":5.5,"color":"#212121","rarity":"★"*9,     "icon":"🌑","stars":9},

    # 10★
    {"name":"God of War",   "hp":999,"atk":300,"def":120,"spd":40,"skill":"Armageddon",  "skill_dmg":6.0,"color":"#ffd600","rarity":"★"*10,    "icon":"⚔️","stars":10},
    {"name":"Creator",      "hp":888,"atk":350,"def":100,"spd":50,"skill":"Genesis",     "skill_dmg":7.0,"color":"#e0e0e0","rarity":"★"*10,    "icon":"✦","stars":10},
    {"name":"Alpha & Omega","hp":999,"atk":250,"def":150,"spd":45,"skill":"Cycle of Life","skill_dmg":0, "color":"#ffffff","rarity":"★"*10,    "icon":"♾️","stars":10},
    {"name":"The End",      "hp":666,"atk":666,"def":66, "spd":66,"skill":"Oblivion",    "skill_dmg":10.0,"color":"#000000","rarity":"★"*10,    "icon":"💀","stars":10},
    {"name":"Chaos Lord",   "hp":850,"atk":400,"def":90, "spd":42,"skill":"Pandemonium", "skill_dmg":7.5,"color":"#311b92","rarity":"★"*10,    "icon":"🌀","stars":10},

    # 11★ (Eternal)
    {"name":"Chrono Empress","hp":1200,"atk":450,"def":180,"spd":55,"skill":"Time Rift",   "skill_dmg":8.5,"color":"#00e5ff","rarity":"★"*11,    "icon":"⏳","stars":11},
    {"name":"Void Singularity","hp":2000,"atk":350,"def":300,"spd":30,"skill":"Black Hole","skill_dmg":9.0,"color":"#1a237e","rarity":"★"*11,    "icon":"🕳️","stars":11},
    {"name":"Galaxy Soul",   "hp":1500,"atk":500,"def":200,"spd":45,"skill":"Cosmic Ray","skill_dmg":8.0,"color":"#7c4dff","rarity":"★"*11,    "icon":"🌌","stars":11},

    # 12★ (Absolute)
    {"name":"The Architect", "hp":2500,"atk":600,"def":400,"spd":60,"skill":"Creation",    "skill_dmg":12.0,"color":"#ffd600","rarity":"★"*12,   "icon":"📐","stars":12},
    {"name":"Oblivion Prime","hp":1800,"atk":800,"def":250,"spd":50,"skill":"Finality",    "skill_dmg":15.0,"color":"#b71c1c","rarity":"★"*12,   "icon":"🌑","stars":12},
    {"name":"The Paradox",   "hp":2200,"atk":700,"def":350,"spd":65,"skill":"Zero Point",  "skill_dmg":13.5,"color":"#ffffff","rarity":"★"*12,   "icon":"❓","stars":12},
]

# Gacha Rates
NORMAL_RATES = {1:49.9, 2:25.0, 3:15.0, 4:8.0, 5:2.0, 6:0.1}
HIGH_RATES = {4:63.89, 5:20.0, 6:10.0, 7:5.0, 8:1.0, 9:0.1, 10:0.01}
SUPER_RATES = {7:65.0, 8:20.0, 9:10.0, 10:4.45, 11:0.5, 12:0.05}

NORMAL_COST = 500
HIGH_COST = 5000
SUPER_COST = 100000

def _roll_from_rates(rates):
    pool = [(s, r) for s, r in rates.items()]
    stars_list = [s for s, _ in pool]; weights = [r for _, r in pool]
    chosen_star = random.choices(stars_list, weights=weights, k=1)[0]
    chars = [c for c in ALL_CHARACTERS if c["stars"] == chosen_star]
    if not chars:
        chars = [c for c in ALL_CHARACTERS if c["stars"] == min(rates.keys())]
    return make_new_char(random.choice(chars))

def roll_normal(): return _roll_from_rates(NORMAL_RATES)
def roll_high(): return _roll_from_rates(HIGH_RATES)
def roll_super(): return _roll_from_rates(SUPER_RATES)

FIXED_STAGES = [
    {"name":"Slime Forest","enemies":[{"name":"Slime","hp":50,"atk":12,"def":4,"spd":5,"color":"#76ff03","icon":"🟢"},{"name":"Big Slime","hp":80,"atk":18,"def":6,"spd":3,"color":"#64dd17","icon":"🟩"}]},
    {"name":"Dark Cave","enemies":[{"name":"Bat","hp":40,"atk":20,"def":3,"spd":14,"color":"#7c4dff","icon":"🦇"},{"name":"Goblin","hp":70,"atk":22,"def":7,"spd":8,"color":"#aed581","icon":"👺"},{"name":"Troll","hp":120,"atk":28,"def":12,"spd":4,"color":"#8d6e63","icon":"👹"}]},
    {"name":"Volcano Peak","enemies":[{"name":"Fire Imp","hp":60,"atk":30,"def":5,"spd":12,"color":"#ff6e40","icon":"😈"},{"name":"Lava Golem","hp":150,"atk":35,"def":18,"spd":3,"color":"#ff3d00","icon":"🌋"},{"name":"Dragon","hp":200,"atk":45,"def":22,"spd":10,"color":"#d50000","icon":"🐉"}]},
    {"name":"Shadow Realm","enemies":[{"name":"Wraith","hp":90,"atk":38,"def":8,"spd":16,"color":"#b388ff","icon":"👻"},{"name":"Demon","hp":180,"atk":42,"def":20,"spd":11,"color":"#ea80fc","icon":"👿"},{"name":"Demon King","hp":300,"atk":55,"def":25,"spd":13,"color":"#aa00ff","icon":"💀"}]},
]
ENEMY_POOL = [
    {"name":"Slime","hp":50,"atk":12,"def":4,"spd":5,"color":"#76ff03","icon":"🟢"},
    {"name":"Goblin","hp":70,"atk":22,"def":7,"spd":8,"color":"#aed581","icon":"👺"},
    {"name":"Troll","hp":120,"atk":28,"def":12,"spd":4,"color":"#8d6e63","icon":"👹"},
    {"name":"Dragon","hp":200,"atk":45,"def":22,"spd":10,"color":"#d50000","icon":"🐉"},
    {"name":"Wraith","hp":90,"atk":38,"def":8,"spd":16,"color":"#b388ff","icon":"👻"},
    {"name":"Demon","hp":180,"atk":42,"def":20,"spd":11,"color":"#ea80fc","icon":"👿"},
    {"name":"Golem","hp":250,"atk":30,"def":28,"spd":3,"color":"#8d6e63","icon":"🗿"},
    {"name":"Lich","hp":160,"atk":50,"def":15,"spd":13,"color":"#ce93d8","icon":"☠️"},
    {"name":"Hydra","hp":300,"atk":40,"def":25,"spd":8,"color":"#26a69a","icon":"🐍"},
    {"name":"Chimera","hp":220,"atk":48,"def":18,"spd":15,"color":"#ef6c00","icon":"🦁"},
]
BIOME_NAMES = ["Cursed Swamp","Frozen Tundra","Abyssal Depths","Sky Fortress","Blood Desert","Void Rift","Crystal Cavern","Nightmare Realm","Inferno Core","Celestial Gate"]

def generate_infinite_stage(stage_idx):
    rng = random.Random(stage_idx)
    extra = stage_idx - len(FIXED_STAGES)
    mult = 1.1 ** extra; stat_m = 1 + extra * 0.08
    num = rng.randint(2, min(3, 2 + extra // 3))
    enemies = []
    for e in rng.sample(ENEMY_POOL, num):
        en = dict(e); en["hp"]=int(en["hp"]*mult); en["atk"]=int(en["atk"]*stat_m); en["def"]=int(en["def"]*stat_m)
        enemies.append(en)
    return {"name": f"{BIOME_NAMES[extra%len(BIOME_NAMES)]} (Lv.{stage_idx+1})", "enemies": enemies}

def get_stage(stage_idx):
    if (stage_idx + 1) % 10 == 0:
        prev_idx = stage_idx - 1
        base_stg = FIXED_STAGES[prev_idx] if prev_idx < len(FIXED_STAGES) else generate_infinite_stage(prev_idx)
        boss_enemies = []
        for e in base_stg["enemies"]:
            en = dict(e)
            en["name"] = "Boss " + en["name"]
            en["hp"] = int(en["hp"] * 1.1); en["atk"] = int(en["atk"] * 1.1); en["def"] = int(en["def"] * 1.1)
            boss_enemies.append(en)
        return {"name": f"Boss Stage {stage_idx+1}", "enemies": boss_enemies, "is_boss": True}
    if stage_idx < len(FIXED_STAGES): return FIXED_STAGES[stage_idx]
    return generate_infinite_stage(stage_idx)

def save_game(data):
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_game():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def delete_save():
    if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
