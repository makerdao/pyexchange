# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2020 MikeHathaway
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
from pprint import pformat
from pyexchange.api import PyexAPI
from pyexchange.okex import OKEXApi

import dateutil.parser

from pymaker import Address, Wad
from pymaker.util import http_response_summary
from typing import Optional, List

class OkcoinApi(OKEXApi):
    """Okcoin API interface.

    Inherits methods from OkEx API which is part of the same company.

    Developed according to the following manuals:
    <https://www.okcoin.com/docs/en/#>.
    <https://github.com/okcoin-okex/open-api-v3-sdk/blob/master/okex-python-sdk-api/okex/client.py>

    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, api_key: str, secret_key: str, password: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(secret_key, str))
        assert(isinstance(password, str))

        super().__init__(api_server, api_key, secret_key, password, timeout)

    def get_markets(self):
        return self._http_get(f"/api/spot/v3/instruments", "")

    # Retrieve address for specified tokens Funding Account
    def get_deposit_address(self, currency: str = "eth") -> str:
        return self._http_get(f"/api/account/v3/deposit/address", f"currency={currency}", requires_auth=True, has_cursor=False)

    # Transfer funds from Funding Account to Spot Trading Account
    def transfer_funds(self, currency: str, amount: Wad) -> bool:
        data = {
            "amount": str(amount),
            "currency": currency,
            "from": 6, # Funding Account
            "to": 1 # Spot Account
        }

        transfer = self._http_post(f"/api/account/v3/transfer", data)

        return transfer["result"]
