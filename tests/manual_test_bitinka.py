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

from pyexchange.bitinka import BitinkaApi
from pymaker import Wad

bitinka = BitinkaApi('https://www.bitinka.com/api/apinka', sys.argv[1], sys.argv[2], 9.5)
# print(bitinka.get_markets())
print(bitinka.get_balances())
print(bitinka.get_trade_balances())
# print(bitinka.get_trades("DAI-USD"))
# print(bitinka.cancel_orders("ETH_DAI"))
# print(bitinka.cancel_order("18718035"))
# print(bitinka.cancel_order(18948425))
print(bitinka.get_orders("ETH-DAI"))




