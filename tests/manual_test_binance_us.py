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
from pymaker import Address, Wad

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)
logging.getLogger("requests").setLevel(logging.INFO)
logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.INFO)

# ctor params: api_server: str, api_key: str, secret_key: str
binance_us = BinanceUsApi("https://api.binance.us", sys.argv[1], sys.argv[2], 9.5)

print("get orders ETH-USD")
print(binance_us.get_orders('ETHUSD'))