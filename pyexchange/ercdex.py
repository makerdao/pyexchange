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

import logging
import requests

from pprint import pformat
from typing import List

import pymaker
from pyexchange.zrxv2 import Order, Pair, ZrxApiV2
from pymaker import Wad, Address
from pymaker.util import bytes_to_hexstring, http_response_summary
from pymaker.sign import eth_sign, to_vrs
from pymaker.token import ERC20Token
from pymaker.zrxv2 import ZrxExchangeV2, ZrxRelayerApiV2, ERC20Asset


class ErcdexApi(ZrxApiV2):
    """Ercdex API interface based on Standard Relayer APIv2 of 0x.

    The only difference with base SRAv2 is cancelation which is not done on-chain but via ErcDEX endpoint.
    """

    def cancel_order(self, order: Order) -> bool:
        assert(isinstance(order, Order))

        order_hash = self.zrx_exchange.get_order_hash(order.zrx_order)
        self.logger.info(f"Cancelling order #{order_hash}...")

        cancel_msg = self.zrx_exchange.web3.sha3(text=f'cancel:{order_hash}')
        v, r, s = to_vrs(eth_sign(cancel_msg, self.zrx_exchange.web3))
        signature = bytes_to_hexstring(bytes([v])) + \
                    bytes_to_hexstring(r)[2:] + \
                    bytes_to_hexstring(s)[2:] + \
                    "03"  # EthSign

        cancel = {"cancellations": [{"orderHash": order_hash, "signature": signature}]}

        response = requests.post(f"{self.zrx_api.api_server}/v2/orders/cancel",
                                 json=cancel,
                                 timeout=self.zrx_api.timeout)
        if response.ok:
            data = response.json()[0]  # We suppose only one cancel
            if data.get('success'):
                self.logger.info(f"Cancelled order #{order_hash}")
                return True
            else:
                self.logger.error(f"Failed to cancel: {http_response_summary(response)}")
                return False
        else:
            self.logger.info(f"Failed to cancel order #{order_hash}")
            return False
