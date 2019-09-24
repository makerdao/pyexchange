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

from pyexchange.fix import FixEngine


class ErisxApi(FixEngine):
    """Abstract baseclass to use with exchanges with we interface with using the FIX
    (Financial Information eXchange) protocol.  This class shall implement common logic for connection management
    and fulfill interface contracts presented by PyexAPI.

    Ideally, subclasses should not need to import simplefix, insulating them from implementation logic within."""

    logger = logging.getLogger()

    def __init__(self, endpoint, sender_comp_id, username, password):
        super(ErisxApi, self).__init__(endpoint, sender_comp_id, "ERISX", username, password)
        self.logon()

    def ticker(self, pair):
        return super().ticker(pair)

    def get_markets(self):
        return super().get_markets()

    def get_pair(self, pair):
        return super().get_pair(pair)

    def get_balances(self):
        return super().get_balances()

    def get_orders(self, pair):
        return super().get_orders(pair)

    def place_order(self, pair, is_sell, price, amount):
        return super().place_order(pair, is_sell, price, amount)

    def cancel_order(self, order_id):
        return super().cancel_order(order_id)

    def get_trades(self, pair, page_number):
        return super().get_trades(pair, page_number)

    def get_all_trades(self, pair, page_number):
        return super().get_all_trades(pair, page_number)
