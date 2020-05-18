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

from pyexchange.coinone import CoinoneApi
from pymaker.numeric import Wad

coinone = CoinoneApi('https://api.coinone.co.kr/', sys.argv[1], sys.argv[2], 9.5)
print("Starting Coinone with the following parameters: ", sys.argv)

# print(coinone.get_markets())

# print(coinone.get_balances())

# print(coinone.place_order('ETH-KRW', True, Wad.from_number(256500.4), Wad.from_number(0.2)))

# print(coinone.get_orders('ETH-KRW'))

# print(coinone.cancel_order('4db8bb7e-1e4d-11e9-9ec7-00e04c3600d7', 'ETH-KRW', Wad.from_number(238100), Wad.from_number(0.1), False))

# print(coinone.get_orders('ETH-KRW'))

# print(coinone.get_trades('ETH-KRW'))
