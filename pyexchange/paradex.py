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

import logging
from typing import Optional

import requests
from web3 import Web3

from pymaker.sign import eth_sign_with_keyfile


class ParadexApi:
    """Paradex API interface.

    Developed according to the following manual:
    <https://github.com/ParadexRelayer/Consumer-API-docs>.
    """

    logger = logging.getLogger()

    def __init__(self, web3: Web3, api_server: str, api_key: str, key_file: str, key_password: str, timeout: float):
        assert(isinstance(web3, Web3))
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(key_file, str))
        assert(isinstance(key_password, str))
        assert(isinstance(timeout, float))

        self.web3 = web3
        self.api_server = api_server
        self.api_key = api_key
        self.key_file = key_file
        self.key_password = key_password
        self.timeout = timeout
        self.nonce = 0

    def ticker(self, pair: str):
        assert(isinstance(pair, str))
        return self._http_get("/v0/ticker", f"market={pair}")

    def get_orders(self, pair: str):
        assert(isinstance(pair, str))

        result = self._http_post("/v0/orders", {
            'market': pair,
            'state': 'open'
        })

        return result

        # orders = filter(self._filter_order, result['orders'])
        # return list(map(self._parse_order, orders))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Paradex API invalid HTTP response: {result.status_code} {result.reason}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Paradex API invalid JSON response: {result.text}")

        if 'error' in data:
            if 'code' in data['error'] and data['error']['code'] == 107:
                new_nonce = data['error']['currentNonce'] + 1
                self.logger.info(f"Invalid nonce, tried {self.nonce - 1} but instructed to change to {new_nonce}")
                self.nonce = new_nonce

                return None

            raise Exception(f"Negative Paradex response: {data}")

        return data

    def _create_signature(self, params: dict) -> str:
        assert(isinstance(params, dict))

        try:
            from sha3 import keccak_256
        except ImportError:
            from sha3 import sha3_256 as keccak_256

        keys = ''
        values = ''
        for key in sorted(params.keys()):
            keys += key
            values += str(params[key])

        raw_message = keccak_256(bytes(keys + values, 'utf-8')).digest()
        return eth_sign_with_keyfile(raw_message, True, self.key_file, self.key_password)

    def _create_vrs_header(self, params: dict):
        assert(isinstance(params, dict))

        signature = self._create_signature(params)
        if signature.endswith("1c"):
            return (signature[0:130] + "01")[2:]
        elif signature.endswith("1b"):
            return (signature[0:130] + "00")[2:]
        else:
            raise Exception(f"Invalid signature: {signature}")

    def _http_get(self, resource: str, params: str):
        assert(isinstance(resource, str))
        assert(isinstance(params, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}?{params}",
                                         headers={"API-KEY": self.api_key},
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        max_attempts = 3
        for attempt in range(0, max_attempts):
            params_with_nonce = params.copy()
            params_with_nonce['nonce'] = self.nonce
            self.nonce += 1

            result = self._result(requests.post(url=f"{self.api_server}{resource}",
                                                json=params_with_nonce,
                                                headers={
                                                    "API-KEY": self.api_key,
                                                    "API-VRS": self._create_vrs_header(params_with_nonce)
                                                },
                                                timeout=self.timeout))

            # result will be `None` if we need to readjust nonce
            # in this case we will try again in the next iteration
            if result is not None:
                return result

        raise Exception(f"Couldn't get a response despite {max_attempts} attempts to readjust the nonce")
