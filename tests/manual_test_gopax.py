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

from pyexchange.gopax import GOPAXApi
from pymaker import Wad

logging.basicConfig(format='%(asctime)-15s %(levelname)-8s %(message)s', level=logging.INFO)

gopax_api = GOPAXApi('https://api.gopax.co.kr', sys.argv[1], sys.argv[2], 9.5)

# print(gopax_api.get_balances())
print(gopax_api.get_all_trades("ZRX-BTC"))
# print(gopax_api.get_orders())
# print(gopax_api.get_trades("ZRX-BTC"))
# print(gopax_api.get_orders())
# print(gopax_api.place_order('ZRX-BTC', True, Wad.from_number(0.00006950), Wad.from_number(10)))
# print(gopax_api.place_order('ZRX-BTC', False, Wad.from_number(0.00006950), Wad.from_number(1)))
# print(gopax_api.get_orders('ZRX-BTC'))
# for order in gopax_api.get_orders('ZRX-BTC'):
#     print(gopax_api.get_order(order.order_id))
# for order in gopax_api.get_orders('ZRX-BTC'):
#     gopax_api.cancel_order(order.order_id)
# print(gopax_api.get_orders())
