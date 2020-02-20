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

import sys

from pyexchange.okcoin import OkcoinApi
from pymaker.numeric import Wad

okcoin = OkcoinApi('https://www.okcoin.com', sys.argv[1], sys.argv[2], sys.argv[3], 9.5)
print("Starting OkcoinAPI with the following parameters: ", sys.argv)

# print(okcoin.get_markets())

print(okcoin.get_balances())

# print(okcoin.get_orders('eth_usd'))

# print(okcoin.get_deposit_address('eth'))

# print(okcoin.place_order('eth_USD', False, Wad.from_number(263.00), Wad.from_number(.05)))

# print(okcoin.cancel_order('eth_usd', '4418069365663744'))

# print(okcoin.get_trades('eth_usd'))

# print(okcoin.get_all_trades("bat_krw"))'''
