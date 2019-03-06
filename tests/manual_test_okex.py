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

from pyexchange.okex import OKEXApi


okex = OKEXApi(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], 15.5)
print("OKEXApi created")

#print(okex.ticker('eth_usdt'))
#print(okex.depth('eth_usdt'))
#print(okex.candles('eth_usdt', '1min'))
print(okex.get_balances())
#print(okex.get_orders('eth_usdt'))
#print(len(okex.get_orders_history('mkr_eth', 1000)))
