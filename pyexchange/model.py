# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re

from pprint import pformat
from typing import Optional

from pymaker import Wad


class Candle:
    def __init__(self, timestamp: int, open: Wad, close: Wad, high: Wad, low: Wad, volume: Wad):
        assert(isinstance(timestamp, int))
        assert(isinstance(open, Wad))
        assert(isinstance(close, Wad))
        assert(isinstance(high, Wad))
        assert(isinstance(low, Wad))
        assert(isinstance(volume, Wad))

        self.timestamp = timestamp
        self.open = open
        self.close = close
        self.high = high
        self.low = low
        self.volume = volume

    def __repr__(self):
        return pformat(vars(self))


class Order:
    def __init__(self,
                 order_id: str,
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert (isinstance(pair, str))
        assert (isinstance(timestamp, int))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, Wad))
        assert (isinstance(amount, Wad))

        self.order_id = order_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount * self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount * self.price

    def __hash__(self):
        return hash((self.order_id,
                     self.timestamp,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_message(item: dict):
        return Order(order_id=item['oid'],
                     timestamp=item['created_at'],
                     pair=item['book'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['amount']))


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 pair: Optional[str],
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str) or (pair is None))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        # Ensure that pair schema matches expectations from sync-trades
        assert(re.match('[a-zA-Z0-9]+\-[a-zA-Z0-9]+', pair))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_message(item: dict):
        return Trade(trade_id=item['oid'],
                     timestamp=item['created_at'],
                     pair=item['book'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['amount']))
