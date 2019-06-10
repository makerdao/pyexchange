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

from pymaker import Address, Wad
from web3 import Web3, HTTPProvider
from pymaker.keys import register_key
from pyexchange.mpx import MpxApi, MpxPair
from pymaker.zrxv2 import ZrxExchangeV2

EXCHANGE_ADDR = Address('0x4f833a24e1f95d70f028921e27040ca56e09ab0b')
DAI_ADDR     = Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359')
WETH_ADDR    = Address('0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2')
FEE_RECIPIENT = Address('0x8752d14a086cee9b8c108611ba9aefe04042c9f9')

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[1]
register_key(web3, sys.argv[2])
zrx_exchange = ZrxExchangeV2(web3, EXCHANGE_ADDR)
pair = MpxPair("WETH-DAI", WETH_ADDR, 18, DAI_ADDR, 18)
api = MpxApi("https://api.mpexchange.io", zrx_exchange, FEE_RECIPIENT, 9.5, None)

print(api.get_markets())
print(api.get_fee_recipients())

order = api.place_order(pair,
                        is_sell=False,
                        price=Wad.from_number(28.8),
                        amount=Wad.from_number(0.7))
print(order)
order = api.place_order(pair,
                        is_sell=True,
                        price=Wad.from_number(300),
                        amount=Wad.from_number(0.1))
print(order)
orders = api.get_orders(pair)
for o in orders:
    print(api.cancel_order(o, None))
print(api.get_orders(pair))
print(api.get_trades("WETH-DAI"))
print(api.get_all_trades("WETH-DAI"))

