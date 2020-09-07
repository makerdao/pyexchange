# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2020 Exef
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

from pyexchange.binance_us import BinanceUsApi
from pyflex import Address, Wad

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)

# ctor params: api_server: str, api_key: str, secret_key: str
binance_us = BinanceUsApi("https://api.binance.us", sys.argv[1], sys.argv[2], 9.5)

print('Get all trades - ETHUSD')
print(binance_us.get_all_trades('ETH-USD'))

print('Get all my account trades - ETHUSD')
print(binance_us.get_trades('ETH-USD'))

print("get orders ETH-USD")
print(binance_us.get_orders('ETH-USD'))

print('get balances')
print(binance_us.get_balances())

print('get ETH balance')
print(binance_us.get_balance('ETH'))

# print('Place order')
# order_id = binance_us.place_order('ETH-USD', False, price=Wad.from_number(420), amount=Wad.from_number(1))

# print('Cancel order')
# print(binance_us.cancel_order(order_id, pair="ETHUSD"))
