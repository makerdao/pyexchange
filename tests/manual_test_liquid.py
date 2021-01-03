# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
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

import sys
import threading

from concurrent.futures import ThreadPoolExecutor
from pyexchange.liquid import LiquidApi
from pymaker import Wad


liquid = LiquidApi("https://api.liquid.com", sys.argv[1], sys.argv[2], 9.5)
_executor = ThreadPoolExecutor(max_workers=5)

data_set = [
        {
            'sell_order_bool': True,
            'price': Wad.from_number(29002),
            'amount': Wad.from_number(0.01)
        },
        {
            'sell_order_bool': True,
            'price': Wad.from_number(29001),
            'amount': Wad.from_number(0.01)
        },
        {
            'sell_order_bool': True,
            'price': Wad.from_number(29000),
            'amount': Wad.from_number(0.01)
        },
        {
            'sell_order_bool': False,
            'price': Wad.from_number(28000),
            'amount': Wad.from_number(0.01)
        },
        {
            'sell_order_bool': False,
            'price': Wad.from_number(28001),
            'amount': Wad.from_number(0.01)
        },
        {
            'sell_order_bool': False,
            'price': Wad.from_number(28002),
            'amount': Wad.from_number(0.01)
        },
        {
            'sell_order_bool': False,
            'price': Wad.from_number(28003),
            'amount': Wad.from_number(0.01)
        }
        ]

for data in data_set:
    _executor.submit(liquid.place_order("BTCDAI", data['sell_order_bool'], data['price'], data['amount']))


# print(liquid.get_markets())
# print(liquid.get_pair("ETHUSDC"))
print(liquid.get_balances())


print("tasks should be complete")
orders = liquid.get_orders("BTCDAI")
print(f"orders {orders}")

for order in orders:
    liquid.cancel_order(str(order.order_id))

# print(liquid.get_trades("ETHUSDC"))
# print(liquid.get_balances())
#print(liquid.cancel_order(str(order_a)))
#print(liquid.cancel_order(str(order_b)))
print(liquid.get_orders("BTCDAI"))
# print(liquid.get_orders("ETHUSDC"))
# print(liquid.get_all_trades("VETETH"))
