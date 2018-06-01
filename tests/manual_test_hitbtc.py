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

import sys

from pyexchange.hitbtc import HitBTCApi
from pymaker.numeric import Wad

api = HitBTCApi('https://api.hitbtc.com', sys.argv[1], sys.argv[2], 9.5)

#print(api.ticker('ETHBTC'))
#print(api.get_balances())
#print(api.get_orders('ETHBTC'))
#print(api.place_order('ETHBTC', False, Wad.from_number(0.05), Wad.from_number(0.1)))
#print(api.get_orders('ETHBTC'))
#for order in api.get_orders('ETHBTC'):
#    print(api.cancel_order(order.order_id))
#print(api.get_orders('ETHBTC'))

print(api.get_trades('ETHBTC'))
print(api.get_all_trades('ETHBTC'))
