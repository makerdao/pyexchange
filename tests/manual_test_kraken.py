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

from pyexchange.kraken import KrakenApi
from pymaker import Wad

kraken = KrakenApi("https://api.kraken.com", sys.argv[1], sys.argv[2], 9.5)

# print(kraken.get_trades('XETHZEUR'))
# kraken.cancel_order('O7Q7Q3-KMCJ3-LT54ZN')
# print(kraken.get_balances())
# order1 = kraken.place_order('ETHDAI', False, Wad.from_number(0.5), Wad.from_number(1))
# order2 = kraken.place_order('XETHZEUR', True, Wad.from_number(5000), Wad.from_number(0.1))
print(kraken.get_orders('ETHDAI'))

# print(kraken.cancel_order(order))
# print(kraken.get_orders('XETHZEUR'))
# # print(kraken.get_balances())
# print(kraken.get_trade_balances())



