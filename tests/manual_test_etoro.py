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

from pyexchange.etoro import EToroApi
from pymaker.numeric import Wad

## Need to convert encrypted private key with empty passphrase to an unencrypted private key file
# openssl pkcs8 -in .etoro-key -out <unencrypted-key-file>

etoro = EToroApi('https://7vriaeqd.hft.etorox.com', sys.argv[1], open('./.etoro-unencrypted-key', 'r').read(), 9.5)
# etoro = EToroApi('https://7vriaeqd.hft.etorox.com', sys.argv[1], open(sys.argv[2], "r",encoding='utf-8').read(), 9.5)

# GET "/api/v1/instruments"
# print(etoro.get_markets())
# print(etoro.get_pair('ETH/USDC'))

# GET "/api/v1/balances"
# print(etoro.get_balances())

# GET "/api/v1/orders"
# print(etoro.get_orders('ethusdc', '10000', 'open', 25))

# POST /api/v1/orders
# print(etoro.place_order('ethusdc', 'buy', Wad.from_number(144.94033), Wad.from_number(.005)))

# DELETE /api/v1/orders/{order_id}
# print(etoro.cancel_order('4ffa71ea-9e33-4cff-80d8-55e3898932ae'))

# GET /api/v1/trades
print(etoro.get_trades('ethusdc', '98479026'))

# GET /api​/v1​/funds​/deposits​/{coin}​/address
# print(etoro.get_deposit_address('eth'))


# f3a8c406-e569-402b-85b6-0bcd102ec856

