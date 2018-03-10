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

import logging
import sys

from web3 import Web3, HTTPProvider

from pyexchange.paradex import ParadexApi
from pymaker import Wad, Address
from pymaker.zrx import ZrxExchange


logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

web3 = Web3(HTTPProvider("http://localhost:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[2]
zrx_exchange = ZrxExchange(web3, Address('0x12459C951127e0c374FF9105DdA097662A027093'))
paradex = ParadexApi(zrx_exchange, 'https://api.paradex.io/consumer', sys.argv[1], 15.5)

print(paradex.get_all_trades('WETH/DAI'))
exit(-1)

# print(paradex.ticker('WETH/DAI'))
print(paradex.get_balances())
print(paradex.get_balances())
print(paradex.get_balances())
print(paradex.get_balances())
print(paradex.get_balances())
print(paradex.get_balances())
# print(paradex.get_orders('WETH/DAI'))

# paradex.place_order('WETH/DAI', True, Wad.from_number(995), Wad.from_number(0.1), expiry=1000)
# for order in paradex.get_orders('WETH/DAI'):
#     paradex.cancel_order(order.order_id)

# print(paradex.get_orders('WETH/DAI'))
# print(paradex.get_trades('WETH/DAI'))
