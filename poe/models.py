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
    def __init__(self, base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                 is_relic, alt_art, quality, implicits, explicits, tags, icon, influences, *args):
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
        self.influences = influences
        self.enchant = None
        self.sockets = None

    def __repr__(self):
        return f"<Item: name={self.name} rarity={self.rarity}>"


class DivCard(Item):
    def __init__(self, base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                 is_relic, alt_art, quality, implicits, explicits, tags, icon, influences, div_data):
        super().__init__(base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                         is_relic, alt_art, quality, implicits, explicits, tags, icon, influences)
        self.card_art = div_data['card_art']
        self.stack_size = div_data['stack_size']
        self.reward_flavor = div_data['reward_flavor']
        self.reward = div_data['reward']


class Prophecy(Item):
    def __init__(self, base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                 is_relic, alt_art, quality, implicits, explicits, tags, icon, influences, proph_data):
        super().__init__(base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                         is_relic, alt_art, quality, implicits, explicits, tags, icon, influences)
        self.prediction = proph_data['prediction text']
        self.objective = proph_data['objective']
        self.seal_cost = proph_data['seal cost']


class Weapon(Item):
    def __init__(self, base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                 is_relic, alt_art, quality, implicits, explicits, tags, icon, influences, weapon_stats):
        super().__init__(base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                         is_relic, alt_art, quality, implicits, explicits, tags, icon, influences)

        self.attack_speed = weapon_stats['attack speed range text']
        self.chaos_min = weapon_stats['chaos damage min range text']
        self.chaos_max = weapon_stats['chaos damage max range text']

        self.cold_min = weapon_stats['cold damage min range text']
        self.cold_max = weapon_stats['cold damage max range text']

        self.fire_min = weapon_stats['fire damage min range text']
        self.fire_max = weapon_stats['fire damage max range text']

        self.lightning_min = weapon_stats['lightning damage min range text']
        self.lightning_max = weapon_stats['lightning damage max range text']

        self.physical_min = weapon_stats['physical damage min range text']
        self.physical_max = weapon_stats['physical damage max range text']

        self.range = f"{weapon_stats['weapon range range text']}"
        self.critical_chance = f"{weapon_stats['critical strike chance range text']}"
        self.quality = 20
    
    @property
    def chaos_damage(self):
        if self.chaos_max != "0" and self.chaos_max != 0:
            return f"{self.chaos_min}-{self.chaos_max}"
        else:
            return None

    @property
    def cold_damage(self):
        if self.cold_max != "0" and self.cold_max != 0:
            return f"{self.cold_min}-{self.cold_max}"
        else:
            return None

    @property
    def fire_damage(self):
        if self.fire_max != "0" and self.fire_max != 0:
            return f"{self.fire_min}-{self.fire_max}"
        else:
            return None

    @property
    def lightning_damage(self):
        if self.lightning_max != "0" and self.lightning_max != 0:
            return f"{self.lightning_min}-{self.lightning_max}"
        else:
            return None

    @property
    def physical_damage(self):
        if self.physical_max != "0" and self.physical_max != 0:
            return f"{self.physical_min}-{self.physical_max}"
        else:
            return None


class Armour(Item):
    def __init__(self, base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                 is_relic, alt_art, quality, implicits, explicits, tags, icon, influences, armour_stats):
        super().__init__(base, item_class, name, rarity, size, drop, requirements, lore, help_text, is_corrupted,
                         is_relic, alt_art, quality, implicits, explicits, tags, icon, influences)
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

        if 'block range average' in armour_stats and armour_stats['block range average']:
            self.block = armour_stats['block range average']
        else:
            self.block = None
        self.quality = 20


class Mod:
    def __init__(self, mod_id, name, group, mod_type, domain, gen_type, level_requirement, stat_text):
        self.mod_id = mod_id
        self.name = name
        self.group = group
        self.type = mod_type
        self.domain = domain
        self.gen_type = gen_type
        self.level_requirement = level_requirement
        self.stat_text = stat_text


class PassiveSkill:
    def __init__(self, asc_class, flavor_text, icon, is_keystone, is_notable, name, reminder_text, stat_text, int_id):
        self.asc_class = asc_class if asc_class else None
        self.flavor_text = flavor_text if flavor_text else None
        self.icon = icon if icon else None
        self.is_keystone = is_keystone
        self.is_notable = is_notable
        self.name = name
        self.reminder_text = reminder_text if reminder_text else None
        self.stat_text = stat_text if stat_text else None
        self.int_id = int_id if int_id else None
        self.tags = []


class Gem:
    def __init__(self, gem_id, cast_time, description, name, weapon_type_restriction, stat_text, quality_bonus,
                 radius, radius_description, radius_secondary, radius_secondary_description, radius_tertiary,
                 radius_tertiary_description, skill_icon, skill_screenshot, inventory_icon, gem_tags, tags,
                 stats_per_level, is_aura, vendors, requirements):
        self.id = gem_id
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
        self.icon = inventory_icon
        self.skill_screenshot = skill_screenshot
        self.gem_tags = gem_tags
        self.tags = tags
        self.stats_per_level = stats_per_level
        self.is_aura = is_aura
        self.vendors = vendors
        self.requirements = requirements
        self.base = None

    def __repr__(self):
        return f"<Gem: name={self.name}>"
