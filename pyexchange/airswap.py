# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017-2018 reverendus, bargst
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
import time
from pprint import pformat
from typing import Optional, List

import requests

from pyexchange.util import sort_trades
from pymaker import Wad, Address
from pymaker.sign import eth_sign
from pymaker.util import hexstring_to_bytes, http_response_summary
from web3 import Web3

class AirswapApi:
    """Airswap API interface.

    Developed according to the following manual:
    <https://developers.airswap.io/#/>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.timeout = timeout

     def set_intents(self, maker_token_address, taker_token_address):
         intents = self._build_intents(maker_token_address, taker_token_address)
         return self._http_post(f"/setIntents", intents)

     def sign_order(self, order):
         return self._http_post(f"/signOrder", order)


    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Airswap API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.text
        except Exception:
            raise Exception(f"Airswap API invalid JSON response: {http_response_summary(result)}")

        if 'status' in data and data['status'] is not 0:
            raise Exception(f"Airswap API negative response: {http_response_summary(result)}")

        return data

    def _http_get(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.get(url=f"{self.api_server}{resource}",
                                         json=params,
                                         timeout=self.timeout))


    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))
        headers = {'content-type': 'application/json'}

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                         json=json.dumps(params),
                                         headers=headers,
                                         timeout=self.timeout))


     def _build_intents(self, maker_token_address, taker_token_address):
         return [{
             "makerToken": maker_token_address,
             "takerToken": taker_token_address,
             "role": "maker"
         }, {
             "makerToken": taker_token_address,
             "takerToken": maker_token_address,
             "role": "maker"
         }]


