# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway
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

from pyexchange.dydx import DydxApi

dydx = DydxApi(sys.argv[1], sys.argv[2])

# print(dydx.get_markets())
# print(dydx.get_pair("WETH-DAI"))

print(dydx.get_balances())

# print(dydx.deposit_funds("USDC", 1.0))

# print(dydx.set_allowances())

# print(dydx.get_balances())

# print(dydx.withdraw_funds("ETH", 0.998))
# print(dydx.withdraw_all_funds("USDC"))

# print(dydx.place_order("WETH-DAI", True, 136.0, 0.1))
# print(dydx.place_order("DAI-USDC", False, 1.0303, 25.0))

# print(dydx.get_orders("WETH-DAI"))

# print(dydx.get_trades("WETH-DAI"))

# print(dydx.cancel_order("0x2619bd0ddaeb4a984bab6c134c132d75d7ec640f026404116ef58ab89c00be77"))


