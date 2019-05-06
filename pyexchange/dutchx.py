# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
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
import requests
from pymaker import Wad, Address
from pymaker.util import http_response_summary
from typing import Optional
from eth_utils import from_wei


class DutchXApi(PyexAPI):
    """Gnosis DutchX API interface https://dutchx.d.exchange/api/docs.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, timeout: float):

        self.api_server = api_server
        self.timeout = timeout

    def get_balance(self, account: Address, coin : Address) -> Wad:
        assert(isinstance(account, Address))
        assert(isinstance(coin, Address))
        balance =  self._http_unauthenticated("GET", f"/v1/accounts/{account.address}/tokens/{coin.address}")
        return Wad.from_number(from_wei(float(balance), 'ether'))

    def _http_unauthenticated(self, method: str, resource: str):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Gnosis DutchX API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Gnosis DutchX API invalid JSON response: {http_response_summary(result)}")

        return data
