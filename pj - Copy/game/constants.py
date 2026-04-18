import random, math, json, os, copy

SAVE_FILE = "savegame.json"
SETTINGS_FILE = "settings.json"
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
            return {"name": f"Boss Armor T{tier}", "desc": f"+{int(val*100)}% to all Stats", "value": val, "type": "armor", "icon": "\U0001f6e1\ufe0f", "color": "#ffb300"}
        if key.startswith("exp_potion_"):
            tier = int(key.split("_")[2])
            if tier == 1: val = 100; name = "EXP Potion I"
            elif tier == 2: val = 500; name = "EXP Potion II"
            elif tier == 3: val = 2000; name = "EXP Potion III"
            else: 
                val = int(2000 * (2.5 ** (tier - 3)))
                name = f"EXP Potion T{tier}"
            return {"name": name, "desc": f"Grants {val:,} EXP", "value": val, "type": "exp", "icon": "\U0001f9ea", "color": "#66bb6a"}
            
        if key not in self:
            return {"name": "Unknown Item", "desc": "???", "value": 0, "type": "loot"}
        return super().__getitem__(key)

ITEMS = ItemDict({
    "buff_atk":     {"name": "ATK Boost",      "icon": "\u2694\ufe0f", "color": "#ef5350", "type": "buff", "stat": "atk", "value": 0.3, "desc": "+30% ATK 1 fight"},
    "buff_def":     {"name": "DEF Boost",      "icon": "\U0001f6e1\ufe0f", "color": "#5c6bc0", "type": "buff", "stat": "def", "value": 0.3, "desc": "+30% DEF 1 fight"},
    "buff_hp":      {"name": "HP Boost",       "icon": "\u2764\ufe0f", "color": "#ec407a", "type": "buff", "stat": "hp",  "value": 0.3, "desc": "+30% HP 1 fight"},
    "gold_bag":     {"name": "Gold Bag",       "icon": "\U0001f4b0", "color": "#ffd740", "type": "gold", "value": 500,  "desc": "+500 Gold"},
    "skip_ticket":  {"name": "Skip Ticket",    "icon": "\U0001f39f\ufe0f", "color": "#f06292", "type": "special", "value": 1,  "desc": "Instantly farm a cleared stage"},
    "forge_stone":  {"name": "Forge Stone",    "icon": "\U0001f528", "color": "#ff6f00", "type": "material", "value": 1,  "desc": "Used to upgrade gear"},
})

GEAR_SLOTS = ["helmet", "chestplate", "legging", "boot", "sword"]
GEAR_ICONS = {"helmet": "\U0001fa96", "chestplate": "\U0001f6e1\ufe0f", "legging": "\U0001f9bf", "boot": "\U0001f462", "sword": "\u2694\ufe0f"}
GEAR_COLORS = {"Common": "#7c7c7c", "Rare": "#448aff", "Epic": "#aa00ff", "Legendary": "#f5c518"}

def _gear_tier_num(floor):
    return floor + 1  # Floor 0 = T1, Floor 1 = T2, etc.

def _gear_tier_color(tier_num):
    if tier_num >= 30: return "#ff1744"   # Red (Mythic+)
    if tier_num >= 20: return "#f5c518"   # Gold (Legendary)
    if tier_num >= 10: return "#aa00ff"   # Purple (Epic)
    if tier_num >= 5: return "#448aff"    # Blue (Rare)
    return "#7c7c7c"                       # Gray (Common)

def _gear_base_val(floor, slot):
    base = 3 + floor * 2
    if slot == "chestplate": return {"def_pct": base, "crit_chance": max(1, floor)}
    if slot == "sword": return {"atk_pct": base, "crit_dmg": max(2, floor)}
    if slot == "boot": return {"spd_pct": base, "def_pct": base // 2, "crit_dmg": max(1, floor // 2)}
    if slot == "helmet": return {"hp_pct": base}
    if slot == "legging": return {"spd_pct": base}
    return {}

def generate_dungeon_gear(floor):
    import uuid
    slot = random.choice(GEAR_SLOTS)
    tier_num = _gear_tier_num(floor)
    base = _gear_base_val(floor, slot)
    names = {
        "helmet": "Helm", "chestplate": "Plate",
        "legging": "Greaves", "boot": "Boots", "sword": "Sword",
    }
    name = f"T{tier_num} {names[slot]}"
    color = _gear_tier_color(tier_num)
    return {
        "id": str(uuid.uuid4()), "name": name, "slot": slot, "tier": f"T{tier_num}",
        "level": 1, "base_stats": base, "icon": GEAR_ICONS[slot],
        "color": color
    }

def get_gear_stats(gear):
    if not gear: return {}
    lvl = gear.get("level", 1)
    result = {}
    for stat, base_val in gear["base_stats"].items():
        # Exponential scaling: 1.04 per level
        result[stat] = int(base_val * (1.04 ** (lvl - 1)))
    return result

def gear_upgrade_cost(gear):
    lvl = gear.get("level", 1)
    return {"forge_stone": lvl + 1, "gold": 500 * lvl}

def get_stage_loot_table(stage_idx):
    tier_1 = max(1, (stage_idx // 10) + 1)
    tier_2 = tier_1 + 1
    table = [(f"exp_potion_{tier_1}", 0.80), (f"exp_potion_{tier_1}", 0.50), ("buff_atk", 0.30), ("buff_def", 0.25)]
    table += [(f"exp_potion_{tier_2}", 0.55), ("buff_hp", 0.30), ("gold_bag", 0.15)]
    if stage_idx >= 3: table += [(f"exp_potion_{tier_2}", 0.40)]
    if stage_idx >= 6: table += [("gold_bag", 0.30)]
    return table

def roll_loot(stage_idx, include_ticket=True):
    table = get_stage_loot_table(stage_idx)
    drops = []
    for key, chance in table:
        if random.random() < chance: drops.append(key)
    if not drops:
        tier_1 = max(1, (stage_idx // 10) + 1); drops.append(f"exp_potion_{tier_1}")
    if include_ticket: drops.append("skip_ticket")
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
    ch["gear"] = {s: None for s in GEAR_SLOTS}
    return ch

def add_exp(char, amount):
    if char["level"] >= MAX_LEVEL: return 0
    char["exp"] += amount; gained = 0
    while char["level"] < MAX_LEVEL and char["exp"] >= exp_for_level(char["level"]+1):
        char["exp"] -= exp_for_level(char["level"]+1); char["level"] += 1; gained += 1
        update_char_stats(char)
    if char["level"] >= MAX_LEVEL: char["exp"] = 0
    return gained

# \u2500\u2500 CHARACTERS \u2500\u2500
ALL_CHARACTERS = [
    # 1\u2605
    {"name":"Slime",        "hp":60, "atk":15,"def":5, "spd":6, "skill":"Bounce [Single]",       "skill_dmg":1.0,"color":"#00e676","stars":1,"target_type":"single","icon":"\U0001f7e2"},
    {"name":"Goblin",       "hp":70, "atk":20,"def":7, "spd":9, "skill":"Stab [Single]",         "skill_dmg":1.3,"color":"#76ff03","stars":1,"target_type":"single","icon":"\U0001f47a"},
    {"name":"Forest Bat",   "hp":45, "atk":18,"def":4, "spd":15,"skill":"Bite [Single]",         "skill_dmg":1.1,"color":"#651fff","stars":1,"target_type":"single","icon":"\U0001f987"},
    {"name":"Cave Rat",     "hp":50, "atk":16,"def":5, "spd":12,"skill":"Scurry [Single]",       "skill_dmg":1.0,"color":"#bdbdbd","stars":1,"target_type":"single","icon":"\U0001f42d"},
    {"name":"Wind Sprite",  "hp":55, "atk":17,"def":4, "spd":18,"skill":"Gust [Single]",         "skill_dmg":1.2,"color":"#1de9b6","stars":1,"target_type":"single","icon":"\U0001f343"},
    {"name":"Rock Crab",    "hp":80, "atk":12,"def":15,"spd":5, "skill":"Pinch [Single]",        "skill_dmg":1.1,"color":"#ff9800","stars":1,"target_type":"single","icon":"\U0001f980"},

    # 2\u2605
    {"name":"Iron Golem",   "hp":180,"atk":25,"def":30,"spd":4, "skill":"Earth Wall [Single]",   "skill_dmg":1.2,"color":"#8d6e63","stars":2,"target_type":"single","icon":"\U0001f6e1\ufe0f"},
    {"name":"Wolf Rider",   "hp":100,"atk":30,"def":10,"spd":14,"skill":"Charge [Single]",       "skill_dmg":1.5,"color":"#8d6e63","stars":2,"target_type":"single","icon":"\U0001f43a"},
    {"name":"Apprentice",   "hp":75, "atk":35,"def":8, "spd":11,"skill":"Magic Bolt [Single]",   "skill_dmg":1.6,"color":"#40c4ff","stars":2,"target_type":"single","icon":"\U0001f9d9"},
    {"name":"Wood Elf",     "hp":85, "atk":32,"def":9, "spd":13,"skill":"Leaf Blade [Single]",   "skill_dmg":1.4,"color":"#00e676","stars":2,"target_type":"single","icon":"\U0001f9dd"},
    {"name":"Skeleton",     "hp":90, "atk":28,"def":12,"spd":10,"skill":"Bone Toss [Single]",    "skill_dmg":1.3,"color":"#e0e0e0","stars":2,"target_type":"single","icon":"\U0001f480"},
    {"name":"Harpy",        "hp":70, "atk":38,"def":6, "spd":16,"skill":"Swoop [Single]",        "skill_dmg":1.6,"color":"#ff5252","stars":2,"target_type":"single","icon":"\U0001f985"},

    # 3\u2605
    {"name":"Blaze Knight", "hp":120,"atk":35,"def":15,"spd":10,"skill":"Flame Slash [Single]","skill_dmg":1.8,"color":"#ff3d00","stars":3,"target_type":"single","icon":"\U0001f525"},
    {"name":"Frost Mage",   "hp":90, "atk":45,"def":10,"spd":12,"skill":"Ice Storm [AoE]",    "skill_dmg":1.2,"color":"#00b0ff","stars":3,"target_type":"aoe","icon":"\u2744\ufe0f"},
    {"name":"Shadow Rogue", "hp":85, "atk":40,"def":8, "spd":18,"skill":"Shadow Strike [Single]","skill_dmg":2.2,"color":"#d500f9","stars":3,"target_type":"single","icon":"\U0001f5e1\ufe0f"},
    {"name":"Holy Priest",  "hp":100,"atk":20,"def":12,"spd":8, "skill":"Divine Heal [AoE]",  "skill_dmg":0,  "color":"#ffc400","stars":3,"target_type":"aoe","icon":"\u2728"},
    {"name":"Wind Archer",  "hp":80, "atk":42,"def":9, "spd":16,"skill":"Gale Arrow [Single]", "skill_dmg":1.9,"color":"#69f0ae","stars":3,"target_type":"single","icon":"\U0001f3f9"},
    {"name":"Stone Monk",   "hp":150,"atk":25,"def":25,"spd":7, "skill":"Iron Fist [Single]",    "skill_dmg":1.7,"color":"#ff9100","stars":3,"target_type":"single","icon":"\U0001f4ff"},
    {"name":"Poison Shaman","hp":95, "atk":35,"def":10,"spd":14,"skill":"Toxic Cloud [AoE]",     "skill_dmg":1.1,"color":"#00e676","stars":3,"target_type":"aoe","icon":"\U0001f9ea"},
    {"name":"Aqua Knight",  "hp":130,"atk":30,"def":20,"spd":9, "skill":"Tidal Slash [Single]","skill_dmg":1.5,"color":"#00b0ff","stars":3,"target_type":"single","icon":"\U0001f30a"},

    # 4\u2605
    {"name":"Dark Lord",    "hp":150,"atk":50,"def":20,"spd":14,"skill":"Void Blast [Single]","skill_dmg":2.5,"color":"#d500f9","stars":4,"target_type":"single","icon":"\U0001f47f"},
    {"name":"Thunder God",  "hp":130,"atk":55,"def":18,"spd":15,"skill":"Lightning [Single]", "skill_dmg":2.4,"color":"#ffea00","stars":4,"target_type":"single","icon":"\u26a1"},
    {"name":"Earth Shaker", "hp":180,"atk":45,"def":25,"spd":8, "skill":"Quake [AoE]",        "skill_dmg":1.3,"color":"#795548","stars":4,"target_type":"aoe","icon":"\U0001f3d7\ufe0f"},
    {"name":"Paladin",      "hp":200,"atk":40,"def":35,"spd":8, "skill":"Holy Shield [Single]","skill_dmg":0, "color":"#ffd600","stars":4,"target_type":"single","icon":"\U0001f6e1\ufe0f"},
    {"name":"Assasin",      "hp":110,"atk":60,"def":12,"spd":22,"skill":"Assasinate [Single]",   "skill_dmg":2.8,"color":"#212121","stars":4,"target_type":"single","icon":"\U0001f977"},
    {"name":"Lava Golem",   "hp":250,"atk":45,"def":25,"spd":5, "skill":"Magma Slam [AoE]",      "skill_dmg":1.4,"color":"#ff3d00","stars":4,"target_type":"aoe","icon":"\U0001f30b"},
    {"name":"Vampire Lord", "hp":140,"atk":55,"def":15,"spd":18,"skill":"Blood Drain [Single]","skill_dmg":2.6,"color":"#d50000","stars":4,"target_type":"single","icon":"\U0001f9db"},
    {"name":"Djinn",        "hp":160,"atk":48,"def":18,"spd":16,"skill":"Wish [AoE]",          "skill_dmg":1.2,"color":"#1de9b6","stars":4,"target_type":"aoe","icon":"\U0001f9de"},

    # 5\u2605
    {"name":"Phoenix",      "hp":180,"atk":65,"def":22,"spd":18,"skill":"Rebirth [Single]",  "skill_dmg":2.8,"color":"#ff3d00","stars":5,"target_type":"single","icon":"\U0001f525"},
    {"name":"Archangel",    "hp":220,"atk":55,"def":30,"spd":16,"skill":"Holy Wrath [AoE]",  "skill_dmg":1.5,"color":"#40c4ff","stars":5,"target_type":"aoe","icon":"\U0001f47c"},
    {"name":"Sun Maiden",   "hp":170,"atk":50,"def":20,"spd":20,"skill":"Solar Heal [AoE]",  "skill_dmg":0,  "color":"#ffea00","stars":5,"target_type":"aoe","icon":"\u2600\ufe0f"},
    {"name":"Sea Kraken",   "hp":250,"atk":70,"def":28,"spd":12,"skill":"Tidal Wave [AoE]",    "skill_dmg":1.6,"color":"#00b0ff","stars":5,"target_type":"aoe","icon":"\U0001f991"},
    {"name":"Griffin",      "hp":200,"atk":60,"def":20,"spd":25,"skill":"Sky Claw [Single]",   "skill_dmg":2.5,"color":"#ffab00","stars":5,"target_type":"single","icon":"\U0001f985"},
    {"name":"Nature Spirit","hp":190,"atk":45,"def":25,"spd":20,"skill":"Forest Bloom [Single]","skill_dmg":0, "color":"#00e676","stars":5,"target_type":"single","icon":"\U0001f33f"},
    {"name":"Werewolf Alpha","hp":210,"atk":68,"def":18,"spd":22,"skill":"Feral Bite [Single]","skill_dmg":2.7,"color":"#795548","stars":5,"target_type":"single","icon":"\U0001f43a"},
    {"name":"Fairy Queen",  "hp":160,"atk":50,"def":15,"spd":24,"skill":"Pixie Dust [AoE]",   "skill_dmg":1.4,"color":"#f50057","stars":5,"target_type":"aoe","icon":"\U0001f9da"},

    # 6\u2605
    {"name":"Dragon King",  "hp":300,"atk":80,"def":40,"spd":20,"skill":"Dragon Breath [AoE]","skill_dmg":1.8,"color":"#d50000","stars":6,"target_type":"aoe","icon":"\U0001f409"},
    {"name":"Storm Caller", "hp":250,"atk":85,"def":30,"spd":22,"skill":"Chain Light [AoE]", "skill_dmg":1.7,"color":"#00e5ff","stars":6,"target_type":"aoe","icon":"\U0001f329\ufe0f"},
    {"name":"Moon Goddess", "hp":260,"atk":75,"def":45,"spd":18,"skill":"Lunar Heal [AoE]",  "skill_dmg":0,  "color":"#d500f9","stars":6,"target_type":"aoe","icon":"\U0001f315"},
    {"name":"Valkyrie",     "hp":290,"atk":95,"def":38,"spd":24,"skill":"Valhalla [Single]",   "skill_dmg":3.3,"color":"#f50057","stars":6,"target_type":"single","icon":"\u2694\ufe0f"},
    {"name":"Death Knight", "hp":280,"atk":85,"def":35,"spd":17,"skill":"Soul Reap [Single]",  "skill_dmg":3.2,"color":"#651fff","stars":6,"target_type":"single","icon":"\U0001f480"},
    {"name":"War Machine",  "hp":350,"atk":90,"def":50,"spd":10,"skill":"Laser Beam [Single]", "skill_dmg":3.1,"color":"#607d8b","stars":6,"target_type":"single","icon":"\U0001f916"},
    {"name":"Ice Dragon",   "hp":310,"atk":78,"def":45,"spd":19,"skill":"Blizzard [AoE]",      "skill_dmg":1.9,"color":"#00b0ff","stars":6,"target_type":"aoe","icon":"\U0001f9ca"},
    {"name":"Shadow Weaver","hp":240,"atk":90,"def":28,"spd":26,"skill":"Dark Web [AoE]",      "skill_dmg":1.6,"color":"#1a237e","stars":6,"target_type":"aoe","icon":"\U0001f578\ufe0f"},

    # 7\u2605
    {"name":"Celestial",    "hp":400,"atk":100,"def":50,"spd":22,"skill":"Star Fall [AoE]",    "skill_dmg":1.8,"color":"#00e5ff","stars":7,"target_type":"aoe","icon":"\u2728"},
    {"name":"Demon Emperor","hp":380,"atk":110,"def":45,"spd":20,"skill":"Hell Storm [Single]","skill_dmg":3.8,"color":"#d50000","stars":7,"target_type":"single","icon":"\U0001f47f"},
    {"name":"Behemoth",     "hp":600,"atk":90, "def":70,"spd":12,"skill":"Earthquake [AoE]",   "skill_dmg":1.6,"color":"#795548","stars":7,"target_type":"aoe","icon":"\U0001f30b"},
    {"name":"Solar Priestess","hp":320,"atk":120,"def":40,"spd":24,"skill":"Sun Grace [Single]","skill_dmg":0, "color":"#ffea00","stars":7,"target_type":"single","icon":"\U0001f31e"},
    {"name":"Abyss Watcher","hp":420,"atk":115,"def":55,"spd":26,"skill":"Void Slash [Single]","skill_dmg":3.6,"color":"#311b92","stars":7,"target_type":"single","icon":"\U0001f441\ufe0f"},
    {"name":"Gargantuan",   "hp":650,"atk":85, "def":80,"spd":10,"skill":"Crush [Single]",     "skill_dmg":3.0,"color":"#5d4037","stars":7,"target_type":"single","icon":"\U0001faa8"},
    {"name":"Storm Bringer","hp":390,"atk":105,"def":42,"spd":28,"skill":"Hurricane [AoE]",    "skill_dmg":1.7,"color":"#40c4ff","stars":7,"target_type":"aoe","icon":"\U0001f32a\ufe0f"},

    # 8\u2605
    {"name":"Titan",        "hp":550,"atk":130,"def":65,"spd":18,"skill":"World Crush [Single]","skill_dmg":4.0,"color":"#ff9100","stars":8,"target_type":"single","icon":"\U0001f5ff"},
    {"name":"Nature Guardian","hp":500,"atk":90, "def":80,"spd":20,"skill":"Grove Heal [AoE]",  "skill_dmg":0,  "color":"#00e676","stars":8,"target_type":"aoe","icon":"\U0001f333"},
    {"name":"Ghost Samurai","hp":480,"atk":160,"def":45,"spd":32,"skill":"Ghost Blade [Single]","skill_dmg":4.5,"color":"#b0bec5","stars":8,"target_type":"single","icon":"\U0001f47b"},
    {"name":"Void Walker",  "hp":450,"atk":150,"def":50,"spd":28,"skill":"Void Rift [Single]", "skill_dmg":4.2,"color":"#651fff","stars":8,"target_type":"single","icon":"\U0001f30c"},
    {"name":"Berserker King","hp":460,"atk":180,"def":40,"spd":22,"skill":"Rage [Single]",      "skill_dmg":4.8,"color":"#ff1744","stars":8,"target_type":"single","icon":"\U0001fa93"},
    {"name":"Eternal Sage", "hp":500,"atk":100,"def":60,"spd":30,"skill":"Ancient Wisdom [Single]","skill_dmg":0,"color":"#d500f9","stars":8,"target_type":"single","icon":"\U0001f52e"},
    {"name":"Mecha Dragon", "hp":580,"atk":140,"def":75,"spd":24,"skill":"Plasma Breath [AoE]","skill_dmg":2.0,"color":"#00b0ff","stars":8,"target_type":"aoe","icon":"\U0001f9be"},

    # 9\u2605
    {"name":"Cosmic Dragon","hp":700,"atk":180,"def":80,"spd":25,"skill":"Nova Blast [AoE]",   "skill_dmg":2.2,"color":"#aa00ff","stars":9,"target_type":"aoe","icon":"\U0001f320"},
    {"name":"Cosmic Caretaker","hp":650,"atk":150,"def":75,"spd":32,"skill":"Universal Heal [AoE]","skill_dmg":0,"color":"#1de9b6","stars":9,"target_type":"aoe","icon":"\U0001f30d"},
    {"name":"Nebula Queen", "hp":550,"atk":220,"def":65,"spd":40,"skill":"Nebula [AoE]",       "skill_dmg":2.3,"color":"#f50057","stars":9,"target_type":"aoe","icon":"\U0001f4ab"},
    {"name":"Time Lord",    "hp":600,"atk":200,"def":70,"spd":35,"skill":"Time Warp [Single]", "skill_dmg":5.0,"color":"#00e5ff","stars":9,"target_type":"single","icon":"\u23f3"},
    {"name":"Star Eater",   "hp":750,"atk":210,"def":85,"spd":28,"skill":"Singularity [Single]","skill_dmg":5.5,"color":"#212121","stars":9,"target_type":"single","icon":"\U0001f311"},
    {"name":"Supernova",    "hp":680,"atk":230,"def":60,"spd":38,"skill":"Explosion [AoE]",    "skill_dmg":2.6,"color":"#ff3d00","stars":9,"target_type":"aoe","icon":"\U0001f4a5"},

    # 10\u2605
    {"name":"God of War",   "hp":999,"atk":300,"def":120,"spd":40,"skill":"Armageddon [AoE]", "skill_dmg":2.5,"color":"#ffea00","stars":10,"target_type":"aoe","icon":"\u2694\ufe0f"},
    {"name":"Creator",      "hp":888,"atk":350,"def":100,"spd":50,"skill":"Genesis [AoE]",    "skill_dmg":2.8,"color":"#ffffff","stars":10,"target_type":"aoe","icon":"\U0001f31f"},
    {"name":"Alpha & Omega","hp":999,"atk":250,"def":150,"spd":45,"skill":"Cycle of Life [AoE]","skill_dmg":0, "color":"#b0bec5","stars":10,"target_type":"aoe","icon":"\u267e\ufe0f"},
    {"name":"The End",      "hp":666,"atk":666,"def":66, "spd":66,"skill":"Oblivion [Single]", "skill_dmg":10.0,"color":"#000000","stars":10,"target_type":"single","icon":"\U0001f480"},
    {"name":"Chaos Lord",   "hp":850,"atk":400,"def":90, "spd":42,"skill":"Pandemonium [AoE]","skill_dmg":2.6,"color":"#311b92","stars":10,"target_type":"aoe","icon":"\U0001f300"},
    {"name":"Omnipotent Eye","hp":777,"atk":450,"def":111,"spd":48,"skill":"All-Seeing [AoE]","skill_dmg":2.9,"color":"#d500f9","stars":10,"target_type":"aoe","icon":"\U0001f441\ufe0f\u200d\U0001f5e8\ufe0f"},

    # 11\u2605
    {"name":"Chrono Empress","hp":1200,"atk":450,"def":180,"spd":55,"skill":"Time Rift [AoE]",  "skill_dmg":3.0,"color":"#00e5ff","stars":11,"target_type":"aoe","icon":"\u23f1\ufe0f"},
    {"name":"Void Singularity","hp":2000,"atk":350,"def":300,"spd":30,"skill":"Black Hole [AoE]","skill_dmg":3.2,"color":"#1a237e","stars":11,"target_type":"aoe","icon":"\U0001f573\ufe0f"},
    {"name":"Galaxy Soul",   "hp":1500,"atk":500,"def":200,"spd":45,"skill":"Cosmic Ray [Single]","skill_dmg":8.0,"color":"#7c4dff","stars":11,"target_type":"single","icon":"\U0001f30c"},
    {"name":"Cosmic Serpent","hp":1800,"atk":480,"def":220,"spd":50,"skill":"Constellation [AoE]","skill_dmg":3.3,"color":"#00e676","stars":11,"target_type":"aoe","icon":"\U0001f409"},

    # 12\u2605
    {"name":"The Architect", "hp":2500,"atk":600,"def":400,"spd":60,"skill":"Creation [AoE]",   "skill_dmg":3.5,"color":"#ffd600","stars":12,"target_type":"aoe","icon":"\U0001f4d0"},
    {"name":"Oblivion Prime","hp":1800,"atk":800,"def":250,"spd":50,"skill":"Finality [Single]","skill_dmg":15.0,"color":"#d50000","stars":12,"target_type":"single","icon":"\U0001f311"},
    {"name":"The Paradox",   "hp":2200,"atk":700,"def":350,"spd":65,"skill":"Zero Point [AoE]","skill_dmg":4.0,"color":"#ffffff","stars":12,"target_type":"aoe","icon":"\u2753"},
    {"name":"Multiverse Weaver","hp":2100,"atk":750,"def":380,"spd":62,"skill":"Reality Shift [AoE]","skill_dmg":4.2,"color":"#d500f9","stars":12,"target_type":"aoe","icon":"\U0001f9f6"},

    # 13\u2605 \u2014 Primordial
    {"name":"Eternal Titan", "hp":3500,"atk":1000,"def":500,"spd":70,"skill":"World End [AoE]",    "skill_dmg":4.5,"color":"#ff6d00","stars":13,"target_type":"aoe","icon":"\U0001f5ff"},
    {"name":"Infinity Blade","hp":2800,"atk":1200,"def":400,"spd":80,"skill":"Infinite Cut [Single]","skill_dmg":20.0,"color":"#e0e0e0","stars":13,"target_type":"single","icon":"\U0001f5e1\ufe0f"},
    {"name":"Astral Healer", "hp":3000,"atk":800, "def":600,"spd":75,"skill":"Cosmos Heal [AoE]",  "skill_dmg":0,  "color":"#b388ff","stars":13,"target_type":"aoe","icon":"\U0001f4ab"},
    {"name":"Dimension Lord","hp":3200,"atk":1100,"def":450,"spd":72,"skill":"Rift Storm [AoE]",  "skill_dmg":4.2,"color":"#1de9b6","stars":13,"target_type":"aoe","icon":"\U0001f300"},
    {"name":"Rift Guardian", "hp":3800,"atk":950, "def":650,"spd":68,"skill":"Seal of Void [Single]","skill_dmg":18.0,"color":"#651fff","stars":13,"target_type":"single","icon":"\U0001f6e1\ufe0f"},

    # 14\u2605 \u2014 Transcendent
    {"name":"Reality Breaker","hp":5000,"atk":1500,"def":700,"spd":90,"skill":"Shatter All [AoE]","skill_dmg":5.0,"color":"#ff1744","stars":14,"target_type":"aoe","icon":"\U0001f48e"},
    {"name":"The Absolute",  "hp":4000,"atk":2000,"def":500,"spd":85,"skill":"Final Slash [Single]","skill_dmg":25.0,"color":"#ffd600","stars":14,"target_type":"single","icon":"\u26a1"},
    {"name":"Void Mother",   "hp":4500,"atk":1200,"def":900,"spd":80,"skill":"Void Embrace [AoE]","skill_dmg":0,  "color":"#6200ea","stars":14,"target_type":"aoe","icon":"\U0001f573\ufe0f"},
    {"name":"Primordial Chaos","hp":5500,"atk":1800,"def":600,"spd":92,"skill":"Big Crunch [AoE]", "skill_dmg":5.5,"color":"#212121","stars":14,"target_type":"aoe","icon":"\U0001f30c"},

    # 15\u2605 \u2014 Omnipotent
    {"name":"\u221e The One",     "hp":9999,"atk":3000,"def":999,"spd":99,"skill":"Omega [AoE]",       "skill_dmg":6.0,"color":"#ffffff","stars":15,"target_type":"aoe","icon":"\u2726"},
    {"name":"Primordial God","hp":8888,"atk":3500,"def":888,"spd":95,"skill":"Big Bang [AoE]",   "skill_dmg":5.5,"color":"#ffd600","stars":15,"target_type":"aoe","icon":"\U0001f31f"},
    {"name":"The True Creator","hp":9999,"atk":3333,"def":999,"spd":100,"skill":"Divine Decree [AoE]","skill_dmg":7.0,"color":"#00e5ff","stars":15,"target_type":"aoe","icon":"\U0001f451"},
]


# Gacha Rates
NORMAL_RATES = {1:49.9, 2:25.0, 3:15.0, 4:8.0, 5:2.0, 6:0.1}
HIGH_RATES = {4:63.89, 5:20.0, 6:10.0, 7:5.0, 8:1.0, 9:0.1, 10:0.01}
SUPER_RATES = {7:65.0, 8:25.0, 9:8.0, 10:1.5, 11:0.4, 12:0.1}
HYPER_RATES = {10:50.0, 11:25.0, 12:14.0, 13:7.0, 14:3.0, 15:1.0}

NORMAL_COST = 500
HIGH_COST = 5000
SUPER_COST = 50000
HYPER_COST = 1000000

RUNE_COST = 25000
RUNE_TIERS = {
    "Common": {"chance": 0.60, "val": 1, "color": "#7c7c7c"},
    "Rare": {"chance": 0.25, "val": 3, "color": "#448aff"},
    "Epic": {"chance": 0.12, "val": 6, "color": "#aa00ff"},
    "Legendary": {"chance": 0.03, "val": 15, "color": "#f5c518"}
}
RUNE_STATS = ["atk", "hp", "def", "spd", "crit_chance", "crit_dmg"]
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
def roll_hyper(): return _roll_from_rates(HYPER_RATES)

def roll_rune():
    r = random.random()
    cumulative = 0.0
    picked_tier = "Common"
    for t_name, t_data in RUNE_TIERS.items():
        cumulative += t_data["chance"]
        if r <= cumulative:
            picked_tier = t_name
            break
            
    stat = random.choice(RUNE_STATS)
    t_info = RUNE_TIERS[picked_tier]
    
    names = {"atk": "Strength", "hp": "Vitality", "def": "Iron", "spd": "Swiftness", "crit_chance": "Precision", "crit_dmg": "Havoc"}
    icons = {"atk": "\u2694\ufe0f", "hp": "\u2764\ufe0f", "def": "\U0001f6e1\ufe0f", "spd": "\u26a1", "crit_chance": "\U0001f3af", "crit_dmg": "\U0001f4a5"}
    
    return {
        "name": f"Rune of {names[stat]}",
        "tier": picked_tier,
        "stat": stat,
        "val": t_info["val"],
        "color": t_info["color"],
        "icon": icons[stat],
        "desc": f"+{t_info['val']}% Global {stat.upper()}"
    }

FIXED_STAGES = [
    {"name":"Slime Forest","enemies":[{"name":"Slime","hp":50,"atk":12,"def":4,"spd":5,"color":"#76ff03","icon":"\U0001f7e2"},{"name":"Big Slime","hp":80,"atk":18,"def":6,"spd":3,"color":"#64dd17","icon":"\U0001f7e9"}]},
    {"name":"Dark Cave","enemies":[{"name":"Bat","hp":40,"atk":20,"def":3,"spd":14,"color":"#7c4dff","icon":"\U0001f987"},{"name":"Goblin","hp":70,"atk":22,"def":7,"spd":8,"color":"#aed581","icon":"\U0001f47a"},{"name":"Troll","hp":120,"atk":28,"def":12,"spd":4,"color":"#8d6e63","icon":"\U0001f479"}]},
    {"name":"Volcano Peak","enemies":[{"name":"Fire Imp","hp":60,"atk":30,"def":5,"spd":12,"color":"#ff6e40","icon":"\U0001f608"},{"name":"Lava Golem","hp":150,"atk":35,"def":18,"spd":3,"color":"#ff3d00","icon":"\U0001f30b"},{"name":"Dragon","hp":200,"atk":45,"def":22,"spd":10,"color":"#d50000","icon":"\U0001f409"}]},
    {"name":"Shadow Realm","enemies":[{"name":"Wraith","hp":90,"atk":38,"def":8,"spd":16,"color":"#b388ff","icon":"\U0001f47b"},{"name":"Demon","hp":180,"atk":42,"def":20,"spd":11,"color":"#ea80fc","icon":"\U0001f47f"},{"name":"Demon King","hp":300,"atk":55,"def":25,"spd":13,"color":"#aa00ff","icon":"\U0001f480"}]},
]
ENEMY_POOL = [
    {"name":"Slime","hp":50,"atk":12,"def":4,"spd":5,"color":"#76ff03","icon":"\U0001f7e2"},
    {"name":"Goblin","hp":70,"atk":22,"def":7,"spd":8,"color":"#aed581","icon":"\U0001f47a"},
    {"name":"Troll","hp":120,"atk":28,"def":12,"spd":4,"color":"#8d6e63","icon":"\U0001f479"},
    {"name":"Dragon","hp":200,"atk":45,"def":22,"spd":10,"color":"#d50000","icon":"\U0001f409"},
    {"name":"Wraith","hp":90,"atk":38,"def":8,"spd":16,"color":"#b388ff","icon":"\U0001f47b"},
    {"name":"Demon","hp":180,"atk":42,"def":20,"spd":11,"color":"#ea80fc","icon":"\U0001f47f"},
    {"name":"Golem","hp":250,"atk":30,"def":28,"spd":3,"color":"#8d6e63","icon":"\U0001f5ff"},
    {"name":"Lich","hp":160,"atk":50,"def":15,"spd":13,"color":"#ce93d8","icon":"\u2620\ufe0f"},
    {"name":"Hydra","hp":300,"atk":40,"def":25,"spd":8,"color":"#26a69a","icon":"\U0001f40d"},
    {"name":"Chimera","hp":220,"atk":48,"def":18,"spd":15,"color":"#ef6c00","icon":"\U0001f981"},
]
BIOME_NAMES = ["Cursed Swamp","Frozen Tundra","Abyssal Depths","Sky Fortress","Blood Desert","Void Rift","Crystal Cavern","Nightmare Realm","Inferno Core","Celestial Gate"]

def generate_infinite_stage(stage_idx):
    rng = random.Random(stage_idx)
    extra = stage_idx - len(FIXED_STAGES)
    if stage_idx >= 50:
        hp_m = (1.08 ** 46) * (1.15 ** (extra - 46)); def_m = (1.03 ** 46) * (1.15 ** (extra - 46))
    else:
        hp_m = 1.08 ** extra; def_m = 1.03 ** extra
    atk_m = 1.04 ** extra
    num = rng.randint(2, min(4, 2 + extra // 5))
    enemies = []
    for e in rng.sample(ENEMY_POOL, num):
        en = dict(e); en["hp"]=int(en["hp"]*hp_m); en["atk"]=int(en["atk"]*atk_m); en["def"]=int(en["def"]*def_m)
        enemies.append(en)
    return {"name": f"{BIOME_NAMES[extra%len(BIOME_NAMES)]} (Lv.{stage_idx+1})", "enemies": enemies}

def generate_dungeon_stage(floor):
    rng = random.Random(floor + 99999)
    mult = 2.0 ** (floor + 1)  # Floor 0 = 2x, Floor 1 = 4x, Floor 2 = 8x, ...
    hp_m = mult; atk_m = mult; def_m = mult
    num = rng.randint(2, min(4, 2 + floor // 3))
    enemies = []
    for e in rng.sample(ENEMY_POOL, num):
        en = dict(e); en["hp"]=int(en["hp"]*hp_m); en["atk"]=int(en["atk"]*atk_m); en["def"]=int(en["def"]*def_m)
        en["name"] = "Dungeon " + en["name"]
        enemies.append(en)
    biome = ["Crimson Depths","Obsidian Halls","Abyssal Forge","Iron Crypt","Shadow Vault"][floor % 5]
    return {"name": f"{biome} F{floor+1}", "enemies": enemies, "is_dungeon": True}

def get_stage(stage_idx):
    if (stage_idx + 1) % 10 == 0:
        prev_idx = stage_idx - 1
        base_stg = FIXED_STAGES[prev_idx] if prev_idx < len(FIXED_STAGES) else generate_infinite_stage(prev_idx)
        boss_enemies = []
        for e in base_stg["enemies"]:
            en = dict(e); en["name"] = "Boss " + en["name"]
            en["hp"] = int(en["hp"] * 2.0); en["atk"] = int(en["atk"] * 1.5); en["def"] = int(en["def"] * 1.5)
            boss_enemies.append(en)
        return {"name": f"Boss Stage {stage_idx+1}", "enemies": boss_enemies, "is_boss": True}
    if stage_idx < len(FIXED_STAGES): return FIXED_STAGES[stage_idx]
    return generate_infinite_stage(stage_idx)

def save_game(data, filename=SAVE_FILE):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_game(filename=SAVE_FILE):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def delete_save(filename=SAVE_FILE):
    if os.path.exists(filename): os.remove(filename)

def preview_save(filename):
    data = load_game(filename)
    if not data: return None
    return {
        "max_stage": data.get("max_stage_cleared", 0),
        "gold": data.get("gold", 500),
        "chars_count": len(data.get("owned_chars", []))
    }

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: pass
    return {}

def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def calc_char_crit(char, equipped_runes=None):
    if equipped_runes is None: equipped_runes = []
    cc = 5.0
    cd = 150.0
    stars = char.get("stars", 1)
    if stars >= 5: cc += (stars - 4) * 0.5
    if stars >= 7: cd += (stars - 6) * 2.0
    cc += char.get("ascension", 0) * 1.0
    
    # Gear
    gear = char.get("gear", {})
    for slot, g in gear.items():
        if not g: continue
        stats = get_gear_stats(g)
        if "crit_chance" in stats: cc += stats["crit_chance"]
        if "crit_dmg" in stats: cd += stats["crit_dmg"]
        
    # Runes
    for r in equipped_runes:
        if not r: continue
        if r.get("stat") == "crit_chance": cc += r.get("val", 0)
        if r.get("stat") == "crit_dmg": cd += r.get("val", 0)
        
    # Crit Chance cap at 75%
    cc = min(75.0, cc)
    return cc, cd
