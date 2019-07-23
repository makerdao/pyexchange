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

import sys
from pyexchange.bittrex import BittrexApi
from pymaker import Wad


bittrex = BittrexApi('https://bittrex.com', sys.argv[1], sys.argv[2], 9.5)

# print(bittrex.get_markets())
# print(bittrex.get_pair('ETH-DAI'))
# print(bittrex.get_all_trades('ETH-DAI'))
# print(f"Balance: {bittrex.get_balances()}")
# order = bittrex.place_order('ETH-DAI', True, Wad.from_number(0.1), Wad.from_number(50))
# order = bittrex.place_order('ETH-DAI', False, Wad.from_number(0.00001), Wad.from_number(50))
# print(f"Placed order: {order}")
# print(f"Balance: {bittrex.get_balances()}")
# print(bittrex.get_trades('ETH-DAI'))
# print(bittrex.get_all_trades('ETH-DAI'))
print(bittrex.cancel_order("16bb9e73-92b6-4e1f-8f59-8d34397eff47"))

print(bittrex.get_orders('ETH-DAI'))
print(f"Balance: {bittrex.get_balances()}")
# print(bittrex.get_all_trades('BTC-AAA'))
