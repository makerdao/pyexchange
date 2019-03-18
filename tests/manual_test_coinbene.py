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

from pyexchange.coinbene import CoinbeneApi
from pymaker import Wad

coinbene = CoinbeneApi('https://api.coinbene.com', sys.argv[1], sys.argv[2], 9.5)

# print(coinbene.ticker("ETHUSDT"))
# print(coinbene.get_pair("ETHUSDT"))
# print(coinbene.get_markets())
# order_id = coinbene.place_order("ETHUSDT", True, Wad.from_number(131), Wad.from_number(0.01))
# print(order_id)
# print(coinbene.get_orders("ETHUSDT"))
coinbene.get_trades("ETHUSDT")