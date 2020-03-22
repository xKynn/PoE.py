import operator
import statistics as stats

import numpy as np


class PriceQuery:
    def __init__(self, league, listings):
        self.league = league
        self.listings = listings

    def lowest(self, results=3):
        return self.listings[:results]

    def fair_price(self):
        prices = [ent['listing']['price'] for ent in self.listings]
        currencies = {}
        for entry in prices:
            if not entry['currency'] in currencies:
                currencies[entry['currency']] = 1
            else:
                currencies[entry['currency']] = currencies[entry['currency']] + 1

        relevant_currency = max(currencies.items(), key=operator.itemgetter(1))[0]
        relevant_prices = [x['amount'] for x in prices if x['currency'] == relevant_currency]
        q3 = np.percentile(relevant_prices, [75, ], interpolation='midpoint')[0]
        prices_for_mean = [x for x in relevant_prices if x <= q3]
        fair_price = stats.mean(prices_for_mean)

        return {'currency': relevant_currency, 'value': fair_price}


class CurrencyQuery(PriceQuery):
    def __init__(self, have, want, league, listings):
        super().__init__(league, listings)
        self.have = have
        self.want = want


class ItemPriceQuery(PriceQuery):
    def __init__(self, name, league, listings):
        super().__init__(league, listings)
        self.name = name
