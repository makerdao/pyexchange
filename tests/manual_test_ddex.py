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
import time

from web3 import Web3, HTTPProvider

from pyexchange.ddex import DdexApi
from pymaker import Wad, Address


logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

web3 = Web3(HTTPProvider("http://127.0.0.1:8545", request_kwargs={"timeout": 600}))
web3.eth.defaultAccount = sys.argv[1]
ddex = DdexApi(web3, 'https://api.ddex.io', 15.5)

#print(ddex.get_markets())
#print(ddex.ticker('DAI-ETH'))
#print(ddex.get_balances())
print(ddex.get_orders('DAI-ETH'))

ddex.place_order('DAI-ETH', True, Wad.from_number(0.003236), Wad.from_number(5))
print(ddex.get_orders('DAI-ETH'))
time.sleep(1)
for order in ddex.get_orders('DAI-ETH'):
    ddex.cancel_order(order.order_id)
print(ddex.get_orders('DAI-ETH'))
