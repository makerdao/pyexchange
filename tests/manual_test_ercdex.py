# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2018 bargst
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
import time

from web3 import Web3, HTTPProvider

from pyexchange.ercdex import Pair, ErcdexApi
from pymaker import Wad, Address
from pymaker.zrxv2 import ZrxExchangeV2, ZrxRelayerApiV2

# Kovan conf
SRAV2_URL = 'https://kovan-staging.ercdex.com/api'
EXCHANGE_ADDR = Address('0x35dd2932454449b14cee11a94d3674a936d5d7b2')
DAI_ADDR     = Address('0xc4375b7de8af5a38a93548eb8453a498222c4ff2')
WETH_ADDR    = Address('0xd0a1e359811322d97991e03f863a0c30c2cf029c')

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = web3.eth.accounts[0]

exchange = ZrxExchangeV2(web3=web3, address=EXCHANGE_ADDR)
api = ZrxRelayerApiV2(exchange=exchange, api_server=SRAV2_URL)
ercdex = ErcdexApi(zrx_exchange=exchange, zrx_api=api)

pair = Pair(WETH_ADDR, 18, DAI_ADDR, 18)
print(ercdex.get_balances(pair))

order = ercdex.place_order(pair, 
                           is_sell=True,
                           price=Wad.from_number(250),
                           amount=Wad.from_number(0.1),
                           expiration=int(time.time())+60*35)

time.sleep(10)
my_orders = ercdex.get_orders(pair, api.get_orders_by_maker(Address(web3.eth.defaultAccount)))
for order in my_orders:
    ercdex.cancel_order(order)
