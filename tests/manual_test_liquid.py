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

from pyexchange.liquid import LiquidApi
from pymaker import Wad

liquid = LiquidApi('https://api.quoine.com', sys.argv[1], sys.argv[2], 9.5)

# print(liquid.get_markets())
# print(liquid.get_pair("ETHUSDC"))
print(liquid.get_balances())
order = liquid.place_order("ETHUSDC", False, Wad.from_number(260), Wad.from_number(0.01))
# print(order)
print(liquid.get_orders("ETHUSDC"))
# print(liquid.get_trades("ETHUSDC"))
# print(liquid.get_balances())
print(liquid.cancel_order(str(order)))
print(liquid.get_orders("ETHUSDC"))
# print(liquid.get_orders("ETHUSDC"))
# print(liquid.get_all_trades("VETETH"))