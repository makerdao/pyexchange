# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 reverendus
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

import logging
import sys

from web3 import Web3, HTTPProvider

from pyexchange.theocean import TheOceanApi, Pair
from pymaker import Address, Wad
from pymaker.zrx import ZrxExchange


logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.DEBUG)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = '0x00531a10c4fBD906313768d277585292AA7C923A'
zrx_exchange = ZrxExchange(web3, Address('0x90fe2af704b34e0224bf2299c838e04d4dcf1364'))

theocean = TheOceanApi(zrx_exchange, 'https://api.staging.theocean.trade/api', sys.argv[1], sys.argv[2], 9.5)

pair = Pair(Address('0x6ff6c0ff1d68b964901f986d4c9fa3ac68346570'), Address('0xd0a1e359811322d97991e03f863a0c30c2cf029c'))


print(theocean.get_market(pair))

# print(theocean.ticker(pair))

print(theocean.get_trades(pair, 1))
print(theocean.get_all_trades(pair, 1))


print(theocean.get_balance(pair.buy_token))
print(theocean.place_order(pair, False, Wad.from_number(0.0015), Wad.from_number(1000)))
print(theocean.get_balance(pair.buy_token))

print(theocean.get_orders(pair))

for order in theocean.get_orders(pair):
    print(theocean.cancel_order(order.order_id))

print(theocean.get_balance(pair.buy_token))
