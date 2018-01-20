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

from pyexchange.gateio import GateIOApi


gate = GateIOApi('https://data.gate.io', sys.argv[1], sys.argv[2], 9.5)

# print (gate.pairs())
# print (gate.tickers())
print (gate.ticker('mkr_eth'))
# print (gate.orderBooks())
print (gate.order_book('btc_usdt'))
print (gate.all_trade_history('btc_usdt'))
print (gate.get_balances())
# print (gate.buy('etc_btc','0.001','123'))
# print (gate.sell('etc_btc','0.001','123'))
# print (gate.cancelOrder('267040896','etc_btc'))
# print (gate.cancelAllOrders('0','etc_btc'))
# print (gate.getOrder('267040896','eth_btc'))
print (gate.get_orders())
print (gate.get_trade_history('etc_btc'))
