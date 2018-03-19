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

import base64
import hashlib
import hmac
import logging
import time

import requests


class GOPAXApi:
    """GOPAX API interface.

    Developed according to the following manual:
    <https://www.gopax.co.kr/API?locale=en>.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, api_secret: str, timeout: float):
        assert(isinstance(api_server, str))
        assert(isinstance(api_key, str))
        assert(isinstance(api_secret, str))
        assert(isinstance(timeout, float))

        self.api_server = api_server
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def get_balances(self):
        return self._http_get("/balances")

    @staticmethod
    def _result(result) -> dict:
        if not result.ok:
            raise Exception(f"GOPAX API invalid HTTP response: {result.status_code} {result.reason}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"GOPAX API invalid JSON response: {result.text}")

        if 'errormsg' in data:
            raise Exception(f"Negative GOPAX response: {data}")

        return data

    def _prepare_headers(self, method: str, request_path: str, request_body: str):
        assert(isinstance(method, str))
        assert(isinstance(request_path, str))
        assert(isinstance(request_body, str))

        nonce = str(time.time())
        headers = {
            "API-KEY": self.api_key,
            "SIGNATURE": self._create_signature(nonce, method, request_path, request_body),
            "NONCE": nonce
        }

        return headers

    def _create_signature(self, nonce: str, method: str, request_path: str, request_body: str):
        assert(isinstance(nonce, str))
        assert(isinstance(method, str))
        assert(isinstance(request_path, str))
        assert(isinstance(request_body, str))

        what = nonce + method + request_path + request_body
        what = bytes(what, "utf-8")

        key = base64.b64decode(self.api_secret)
        signature = hmac.new(key, what, hashlib.sha512)

        return base64.b64encode(signature.digest())

    def _http_get(self, resource: str):
        assert(isinstance(resource, str))

        return self._result(requests.get(url=f"{self.api_server}{resource}",
                                         headers=self._prepare_headers('GET', resource, ''),
                                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert(isinstance(resource, str))
        assert(isinstance(params, dict))

        #TODO
