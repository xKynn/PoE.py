class ClientBase:
    valid_item_filters = ['base', 'class', 'name', 'rarity', 'size_x', 'size_y', 'drop_leagues',
                          'required_dexterity', 'required_strength', 'required_intelligence',
                          'required_level', 'stat_text', 'implicit_stat_text', 'quality',
                          'explicit_stat_text', 'is_corrupted', 'is_relic', 'flavour_text',
                          'help_text', 'drop_areas', 'drop_enabled', 'drop_level',
                          'drop_level_maximum', 'drop_text']

    @staticmethod
    def extract_cargoquery(data):
        extracted = []
        for item in data['cargoquery']:
            extracted.append(item['title'])
        return extracted

    @staticmethod
    def bool_(val):
        return bool(int(val))
