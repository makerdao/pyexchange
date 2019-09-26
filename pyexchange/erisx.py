# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 EdNoepel
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

from pyexchange.api import PyexAPI
from pyexchange.fix import FixEngine


class ErisxApi(PyexAPI):
    """Implementation logic for interacting with the ErisX exchange, which uses FIX for order management and
    market data, and a WebAPI for retrieving account balances."""

    logger = logging.getLogger()

    def __init__(self, endpoint, sender_comp_id, username, password):
        self.fix = FixEngine(endpoint, sender_comp_id, "ERISX", username, password)
        self.fix.logon()

    def ticker(self, pair):
        # TODO: Subscribe to L1 data, await receipt, and then unsubscribe and return the data.
        raise NotImplementedError()

    def get_markets(self):
        # TODO: Send 35=x, await 35=y
        raise NotImplementedError()

    def get_pair(self, pair):
        # TODO: receive a 35=f (not sure how to request it)
        raise NotImplementedError()

    def get_balances(self):
        # TODO: Call into the /accounts method of ErisX Clearing WebAPI, which provides a balance of each coin.
        # They also offer a detailed /balances API, which I don't believe we need at this time.
        raise NotImplementedError()

    def get_orders(self, pair):
        # TODO: Send 35=MA, await 35=8, map the executions by tag 37 (OrderID) to build order state
        raise NotImplementedError()

    def place_order(self, pair, is_sell, price, amount):
        # TODO: Send 35=D; await the execution report confirming order is placed
        raise NotImplementedError()

    def cancel_order(self, order_id):
        # TODO: Send 35=F
        raise NotImplementedError()

    def get_trades(self, pair, page_number):
        # TODO: like get_orders, send a 35=MA, filter out any open orders (not partially filled)
        raise NotImplementedError()

    def get_all_trades(self, pair, page_number):
        raise NotImplementedError()
