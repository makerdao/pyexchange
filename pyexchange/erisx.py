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


class ErisxApi():
    """Abstract baseclass to use with exchanges with we interface with using the FIX
    (Financial Information eXchange) protocol.  This class shall implement common logic for connection management
    and fulfill interface contracts presented by PyexAPI.

    Ideally, subclasses should not need to import simplefix, insulating them from implementation logic within."""

    logger = logging.getLogger()

    def __init__(self, endpoint, sender_comp_id, username, password):
        self.fix = FixEngine(endpoint, sender_comp_id, "ERISX", username, password)
        self.fix.logon()

    def ticker(self, pair):
        raise NotImplementedError()

    def get_markets(self):
        raise NotImplementedError()

    def get_pair(self, pair):
        raise NotImplementedError()

    def get_balances(self):
        # TODO: Call into their WebAPI which provides account balances
        raise NotImplementedError()

    def get_orders(self, pair):
        raise NotImplementedError()

    def place_order(self, pair, is_sell, price, amount):
        # TODO: Send 35=D
        raise NotImplementedError()

    def cancel_order(self, order_id):
        # TODO: Send 35=F
        raise NotImplementedError()

    def get_trades(self, pair, page_number):
        raise NotImplementedError()

    def get_all_trades(self, pair, page_number):
        raise NotImplementedError()
