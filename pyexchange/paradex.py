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

import hashlib
import logging
import urllib
import hmac
from _pysha3 import keccak_256
from pprint import pformat
from typing import List, Optional

import requests
from eth_utils import force_bytes
from web3 import Web3

from pyexchange.util import get_db_file, get_db, get_lock, filter_trades, sort_trades
from pymaker.numeric import Wad
from pymaker.util import eth_sign


class ParadexApi:
    """Paradex API interface.

    Developed according to the following manual:
    <https://github.com/ParadexRelayer/Consumer-API-docs>.
    """

    logger = logging.getLogger()

    def __init__(self, web3: Web3, api_server: str, api_key: str, timeout: float):
        assert(isinstance(web3, Web3))
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(timeout, float))

        self.web3 = web3
        self.api_server = api_server
        self.api_key = api_key
        self.timeout = timeout

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/v0/ticker", f"market={pair}")

    def get_orders(self, pair: str):
        assert(isinstance(pair, str))

        result = self._http_post("/v0/orders", {
            'market': pair,
            'state': 'open',
            'nonce': 8
        })

        return result

        # orders = filter(self._filter_order, result['orders'])
        # return list(map(self._parse_order, orders))

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"Paradex API invalid HTTP response: {result.status_code} {result.reason}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Paradex API invalid JSON response: {result.text}")

        if 'error' in data:
            raise Exception(f"Negative Paradex response: {data}")

        return data

    def _create_signature(self, params):
        assert(isinstance(params, dict))

        keys = ''
        values = ''
        for key in sorted(params.keys()):
            keys += key
            values += str(params[key])
        sign = keys + values

        sign = keccak_256(force_bytes(sign)).digest()

        # signature = eth_sign(self.web3, bytes(sign, 'utf-8'))
        signature = eth_sign(self.web3, sign)

        print(signature)
        return signature

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         headers={"API-KEY": self.api_key},
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                          json=params,
                                          headers={"API-KEY": self.api_key, "API-VRS": self._create_signature(params)[2:]},
                                          timeout=self.timeout))
