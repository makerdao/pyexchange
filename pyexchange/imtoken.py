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
from pprint import pformat
from pyexchange.api import PyexAPI
import requests
import json
from pymaker import Contract, Address, Transact, Wad
from pymaker.util import http_response_summary
from typing import Optional, List
from web3 import Web3


class Trade:
    def __init__(self,
                 trade_id: str,
                 timestamp: int,
                 maker_token: str,
                 taker_token: str,
                 maker_token_amount: Wad,
                 taker_token_amount: Wad):
        assert(isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(maker_token, str))
        assert(isinstance(taker_token, str))
        assert(isinstance(maker_token_amount, Wad))
        assert(isinstance(taker_token_amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.maker_token = maker_token
        self.taker_token = taker_token
        self.maker_token_amount = maker_token_amount
        self.taker_token_amount = taker_token_amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.maker_token == other.maker_token and \
               self.taker_token == other.taker_token and \
               self.maker_token_amount == other.maker_token_amount and \
               self.taker_token_amount == other.taker_token_amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.maker_token,
                     self.taker_token,
                     self.maker_token_amount,
                     self.taker_token_amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_list(trade):
        return Trade(trade_id=trade['quoteId'],
                     timestamp=trade['timestamp'],
                     maker_token=trade['makerToken'],
                     taker_token=trade['takerToken'],
                     maker_token_amount=Wad.from_number(trade['makerTokenAmount']),
                     taker_token_amount=Wad.from_number(trade['takerTokenAmount']))


class ImtokenApi(PyexAPI):
    """ImtokenApi API interface.
    """

    logger = logging.getLogger()

    def __init__(self, api_server: str, timeout: float):
        assert(isinstance(api_server, str))

        self.api_server = api_server
        self.timeout = timeout

    def get_balances(self):
        return self._http_unauthenticated("GET", "/getBalances", {})['balances']

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))

        result = self._http_unauthenticated("GET", f"/getOrdersHistory?page={page_number}&perpage=100", {})['orders']
        result = list(filter(lambda item: item['status'] == 'success', result))

        return list(map(lambda item: Trade.from_list(item), result))

    def _http_unauthenticated(self, method: str, resource: str, body: dict):
        assert(isinstance(method, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None))

        data = json.dumps(body, separators=(',', ':'))

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{resource}",
                                             data=data,
                                             timeout=self.timeout))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Imtoken API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Imtoken API invalid JSON response: {http_response_summary(result)}")

        return data


class ImToken(Contract):
    """A client for the ImToken proxy exchange contract.

    Attributes:
        web3: An instance of `Web` from `web3.py`.
        address: Ethereum address of the `ImToken` proxy contract.
    """

    abi = Contract._load_abi(__name__, 'abi/IMTOKEN.abi')

    def __init__(self, web3: Web3, address: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(address, Address))

        self.web3 = web3
        self.address = address
        self._contract = self._get_contract(web3, self.abi, address)

    def withdraw(self, amount: Wad, token: Address, to: Address) -> Transact:
        """Withdraws `amount` of `token` from ImToken proxy contract `to` address.

        Args:
            amount: Amount of Token to be withdrawn from ImToken.
            token: Token address to be withdrawn from ImToken.
            to: Address to send Tokens from ImToken

        Returns:
            A :py:class:`pymaker.Transact` instance, which can be used to trigger the transaction.
        """
        assert(isinstance(amount, Wad))
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'withdraw',
                        [token.address, to.address, amount.value])
