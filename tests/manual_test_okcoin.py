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

okcoin = OkcoinApi('https://www.okcoin.com/api', sys.argv[1], sys.argv[2], 9.5)
print("Starting OkcoinAPI with the following parameters: ", sys.argv)

# GET "/api/v1/instruments"
# print(okcoin.get_markets())
# print(okcoin.get_pair('ETH/USDC'))

# GET "/api/v1/balances"
# print(okcoin.get_balances())

# GET "/api/v1/orders"
# print(okcoin.get_orders('dai_krw'))

# POST /api/v1/orders
# print(okcoin.place_order('dai_krw', False, Wad.from_number(1500), Wad.from_number(5)))

# DELETE /api/v1/orders/{order_id}
# print(okcoin.cancel_order(249334, 'dai_krw'))

# GET /api/v1/trades
# print(okcoin.get_trades('dai_krw'))

print(okcoin.get_all_trades("bat_krw"))