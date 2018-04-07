# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus
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
import logging
import sys

from pyexchange.ethfinex import EthfinexApi
from pymaker import Wad


logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

ethfinex = EthfinexApi('https://api.ethfinex.com', sys.argv[1], sys.argv[2], 9.5)

# for order in ethfinex.get_orders('ZRXETH'):
#     ethfinex.cancel_order(order.order_id)
# exit(-1)

# print(ethfinex.place_order("ZRXETH", False, Wad.from_number(0.0010), Wad.from_number(25)))
for _ in range(0, 1000):
    print(ethfinex.get_orders('ZRXETH'))
exit(-1)
print(ethfinex.get_balances())
print(ethfinex.get_trades('ZRXETH'))
exit(-1)
print(ethfinex.get_orders('ZRXETH'))
# print(ethfinex.get_trades("BTCUSD"))
# print(ethfinex.get_all_trades('BTCUSD'))

print(ethfinex.place_order("ZRXETH", False, Wad.from_number(0.0010), Wad.from_number(25)))

print(ethfinex.get_orders('ZRXETH'))
print(ethfinex.get_balances())

for order in ethfinex.get_orders('ZRXETH'):
    ethfinex.cancel_order(order.order_id)
print(ethfinex.get_orders('ZRXETH'))
