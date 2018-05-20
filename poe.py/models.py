from .utils import initializer


class BaseItem:
    def __init_(self, name, item_id, page_url):
        self.name = name
        self.id = item_id
        self.page_url = page_url


class ItemDrop:
    @initializer
    def __init__(self, enabled, level, max_level, leagues, areas, text):
        pass


class Requirements:
    @initializer
    def __init__(self, dex, str, int, level):
        pass


class Item:
    @initializer
    def __init__(self, base, item_class, name, rarity, size, drop, requirements, lore,
                 help_text, is_corrupted, is_relic, alt_art, quality,
                 implicits, explicits):
        pass

    def __repr__(self):
        return f"<Item: name={self.name} rarity={self.rarity}"

class Mod:
    @initializer
    def __init__(self, mod_id, name, group, type, domain, gen_type,
                 level_requirement, stat_text):
        pass


class Gem:
    @initializer
    def __init__(self, id, cast_time, description, name, weapon_type_restriction,
                 projectile_speed, stat_text, quality_bonus, radius, radius_description,
                 radius_secondary, radius_secondary_description, radius_tertiary,
                 radius_tertiary_description, skill_icon, skill_id, skill_screenshot):
        pass
