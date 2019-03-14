# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 Liquidity Providers LLC
#
# This program is distributed WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

import time
import pytest

from pymaker import Wad
from pyexchange.okex import Order


class TestOKEX:
    def test_order(self):
        price = Wad.from_number(4.8765)
        amount = Wad.from_number(0.222)
        filled_amount = Wad.from_number(0.153)
        order = Order(
            order_id="153153",
            timestamp=int(time.time()),
            pair="MKR-ETH",
            is_sell=False,
            price=price,
            amount=amount,
            filled_amount=filled_amount
        )
        assert(order.price == order.sell_to_buy_price)
        assert(order.price == order.buy_to_sell_price)
        assert(order.remaining_buy_amount == amount-filled_amount)
        assert(order.remaining_sell_amount == (amount-filled_amount)*price)