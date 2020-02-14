# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MakerDAO
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

from pyexchange.bitso import BitsoApi
from pymaker.numeric import Wad

bitso = BitsoApi('https://api.bitso.com', sys.argv[1],  sys.argv[2], 9.5)
print("Starting BitsoApi with the following parameters: ", sys.argv)

# GET "/v3/balance/"
# print(bitso.get_balances())

#print(bitso.get_markets())
# print(bitso.get_pair('ETH/USDC'))

# GET "/api/v1/orders"
# print(bitso.get_orders('eth_mxn'))

# POST /api/v1/orders
print(bitso.place_order('eth_mxn', 'sell', 5000.000, .01))

# DELETE /api/v1/orders/{order_id}
# print(bitso.cancel_order('MCFChw1RyAStLVnM'))

# GET /api/v1/trades
# print(bitso.get_trades("eth_mxn"))
# print(bitso.get_trades('ethusdc', '1578959828'))

# GET /api​/v1​/funds​/deposits​/{coin}​/address
# print(bitso.get_deposit_address('eth'))
