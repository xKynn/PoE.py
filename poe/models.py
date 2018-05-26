class BaseItem:
    def __init_(self, name, item_id, page_url):
        self.name = name
        self.id = item_id
        self.page_url = page_url


class ItemDrop:
    def __init__(self, enabled, level, max_level, leagues, areas, text):
        self.enabled = enabled
        self.level = level
        self.max_level = max_level
        self.leagues = leagues
        self.areas = areas
        self.text = text


class Requirements:
    def __init__(self, dex, stren, intel, level):
        self.dex = int(dex) if dex.isdigit() else None
        self.str = int(stren) if stren.isdigit() else None
        self.int = int(intel) if intel.isdigit() else None
        self.level = int(level) if level.isdigit() and int(level) >= 1 else None

    @property
    def has_reqs(self):
        return any([self.dex, self.str, self.int, self.level])


class Item:
    def __init__(self, base, item_class, name, rarity, size, drop, requirements,
                 lore, help_text, is_corrupted, is_relic, alt_art, quality, implicits, explicits, tags, icon, *args):
        self.base = base
        self.item_class = item_class
        self.name = name
        self.rarity = rarity
        self.size = size
        self.drop = drop
        self.requirements = requirements
        self.lore = lore
        self.help_text = help_text
        self.is_corrupted = is_corrupted
        self.is_relic = is_relic
        self.alt_art = alt_art
        self.quality = quality
        self.implicits = implicits
        self.explicits = explicits
        self.tags = tags
        self.icon = icon

    def __repr__(self):
        return f"<Item: name={self.name} rarity={self.rarity}>"


class Weapon(Item):
    def __init__(self, base, item_class, name, rarity, size, drop, requirements,
                 lore, help_text, is_corrupted, is_relic, alt_art, quality, implicits, explicits, tags, icon,
                 weapon_stats):
        super().__init__(base, item_class, name, rarity, size, drop, requirements,
                         lore, help_text, is_corrupted, is_relic, alt_art, quality, implicits, explicits, tags, icon)
        #print(weapon_stats)
        self.attack_speed = weapon_stats['attack speed range text']
        if weapon_stats['chaos damage max range text'] != '0':
            self.chaos_damage = f"{weapon_stats['chaos damage min range text']}-" \
                                f"{weapon_stats['chaos damage max range text']}"
        else:
            self.chaos_damage = None
        if weapon_stats['cold damage max range text'] != '0':
            self.cold_damage = f"{weapon_stats['cold damage min range text']}-" \
                               f"{weapon_stats['cold damage max range text']}"
        else:
            self.cold_damage = None
        if weapon_stats['fire damage max range text'] != '0':
            self.fire_damage = f"{weapon_stats['fire damage min range text']}-" \
                               f"{weapon_stats['fire damage max range text']}"
        else:
            self.fire_damage = None
        if weapon_stats['lightning damage max range text'] != '0':
            self.lightning_damage = f"{weapon_stats['lightning damage min range text']}-" \
                                    f"{weapon_stats['lightning damage max range text']}"
        else:
            self.lightning_damage = None
        if weapon_stats['physical damage max range text'] != '0':
            self.physical_damage = f"{weapon_stats['physical damage min range text']}-" \
                                   f"{weapon_stats['physical damage max range text']}"
        else:
            self.physical_damage = None
        self.range = f"{weapon_stats['range range text']}"
        self.critical_chance = f"{weapon_stats['critical strike chance range text']}"
        self.quality = "+20%"


class Armour(Item):
    def __init__(self, base, item_class, name, rarity, size, drop, requirements,
                 lore, help_text, is_corrupted, is_relic, alt_art, quality, implicits, explicits, tags, icon,
                 armour_stats):
        super().__init__(base, item_class, name, rarity, size, drop, requirements,
                         lore, help_text, is_corrupted, is_relic, alt_art, quality, implicits, explicits, tags, icon)
        if armour_stats['armour range text'] != '0':
            self.armour = armour_stats['armour range text']
        else:
            self.armour = None
        if armour_stats['evasion range text'] != '0':
            self.evasion = armour_stats['evasion range text']
        else:
            self.evasion = None
        if armour_stats['energy shield range text'] != '0':
            self.energy_shield = armour_stats['energy shield range text']
        else:
            self.energy_shield = None
        self.quality = "+20%"


class Mod:
    def __init__(self, mod_id, name, group, type, domain, gen_type, level_requirement, stat_text):
        self.mod_id = mod_id
        self.name = name
        self.group = group
        self.type = type
        self.domain = domain
        self.gen_type = gen_type
        self.level_requirement = level_requirement
        self.stat_text = stat_text


class Gem:
    def __init__(self, id, cast_time, description, name, weapon_type_restriction, stat_text,
                 quality_bonus, radius, radius_description,
                 radius_secondary, radius_secondary_description, radius_tertiary,
                 radius_tertiary_description, skill_icon, skill_screenshot,
                 stats_per_level, is_aura, vendors):
        self.id = id
        self.cast_time = cast_time
        self.description = description
        self.name = name
        self.weapon_type_restriction = weapon_type_restriction
        self.stat_text = stat_text
        self.quality_bonus = quality_bonus
        self.radius = radius
        self.radius_description = radius_description
        self.radius_secondary = radius_secondary
        self.radius_secondary_description = radius_secondary_description
        self.radius_tertiary = radius_tertiary
        self.radius_tertiary_description = radius_tertiary_description
        self.skill_icon = skill_icon
        self.skill_screenshot = skill_screenshot
        self.stats_per_level = stats_per_level
        self.is_aura = is_aura
        self.vendors = vendors

    def __repr__(self):
        return f"<Gem: name={self.name}>"
