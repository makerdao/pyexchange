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
import json
import random

from pprint import pformat
from typing import Optional, List, Iterable, Iterator

import requests

from pymaker import Address
from pymaker.util import hexstring_to_bytes, http_response_summary
from web3 import Web3

from typing import Optional, List, Iterable, Iterator

from hexbytes import HexBytes
from web3 import Web3
from web3.utils.events import get_event_data

from pymaker import Contract, Address, Transact, Receipt
from pymaker.numeric import Wad
from pymaker.token import ERC20Token
from pymaker.util import int_to_bytes32, bytes_to_int


class Filled:
    def __init__(self, log):
        self.order_id = bytes_to_int(log['transactionHash'])
        self.maker = Address(log['args']['makerAddress'])
        self.maker_token = Address(log['args']['makerToken'])
        self.maker_amount = Wad(log['args']['makerAmount'])
        self.taker = Address(log['args']['takerAddress'])
        self.taker_token = Address(log['args']['takerToken'])
        self.taker_amount = Wad(log['args']['takerAmount'])
        self.raw = log

    def __eq__(self, other):
        assert(isinstance(other, Filled))
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return pformat(vars(self))


class AirswapContract(Contract):
    """A client for a `Airswap` contract.

    `AirwapContract` is a simple on-chain OTC market for ERC20-compatible tokens.

    Attributes:
        web3: An instance of `Web` from `web3.py`.
        address: Ethereum address of the `Airswap` contract.
        past_blocks: Number of past ethereum blocks to query
    """

    abi = Contract._load_abi(__name__, 'abi/Airswap.abi')
    bin = Contract._load_bin(__name__, 'abi/Airswap.bin')

    def __init__(self, web3: Web3, address: Address, past_blocks):
        assert(isinstance(web3, Web3))
        assert(isinstance(address, Address))

        self.web3 = web3
        self.address = address
        self.past_blocks = past_blocks
        self._contract = self._get_contract(web3, self.abi, address)


    def past_fill(self, number_of_past_blocks: int, event_filter: dict = None) -> List[Filled]:
        """Synchronously retrieve past Fill events.
        `Fill` events are emitted by the Airswap contract every time someone fills and order.
        Args:
            number_of_past_blocks: Number of past Ethereum blocks to retrieve the events from.
            event_filter: Filter which will be applied to returned events.
        Returns:
            List of past `Fill` events represented as :py:class:`pymaker.oasis.LogTake` class.
        """
        assert(isinstance(number_of_past_blocks, int))
        assert(isinstance(event_filter, dict) or (event_filter is None))

        return self._past_events(self._contract, 'Filled', Filled, number_of_past_blocks, event_filter)


    def get_trades(self, pair, page_number: int = 1):
        assert(isinstance(page_number, int))

        fills = self.get_all_trades(pair, page_number)
        address = Address(self.web3.eth.defaultAccount)

        # Filter trades from address
        fills = [fill for fill in fills
                if fill.maker == address or
                   fill.taker == address]

        return fills


    def get_all_trades(self, pair, page_number: int = 1):
        assert(page_number == 1)

        fills = self.past_fill(self.past_blocks)

        # Filter trades for addresses in pair
        fills = [fill for fill in fills
                if fill.maker_token in pair and
                   fill.taker_token in pair]

        return fills


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

    def set_intents(self,
                    buy_token: Address,
                    sell_token: Address,
                    alt_sell_token: Address):

        assert(isinstance(buy_token, Address))
        assert(isinstance(sell_token, Address))
        assert(isinstance(alt_sell_token, Address))

        intents = self._build_intents(buy_token.__str__(),
                                      sell_token.__str__()) + \
                  self._build_intents(buy_token.__str__(),
                                      alt_sell_token.__str__())

        return self._http_post("/setIntents", intents)

    def sign_order(self,
                   maker_address,
                   maker_token,
                   maker_amount,
                   taker_address,
                   taker_token,
                   taker_amount):

        order = self._build_order(maker_address,
                                  maker_token,
                                  maker_amount,
                                  taker_address,
                                  taker_token,
                                  taker_amount)

        return self._http_post("/signOrder", order)


    def approve(self, buy_token: Address, sell_token: Address):
        assert(isinstance(buy_token, Address))
        assert(isinstance(sell_token, Address))

        try:
            buy_token_data = self._build_approve(buy_token.__str__())
            sell_token_data = self._build_approve(sell_token.__str__())

            self._http_post("/approveTokenForTrade", buy_token_data)
            self._http_post("/approveTokenForTrade", sell_token_data)
            logging.getLogger().info(f"token approval success: {buy_token.__str__()}, {sell_token.__str__()}")
            return 'ok'

        except Exception as e:
             logging.getLogger().exception(f"Encountered an error when attempting to approve tokens with Airswap contract({e}).")


    def _build_approve(self, token):
        return {"tokenContractAddr": token}

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

    def _http_post(self, resource: str, params):
        assert(isinstance(resource, str))
        return self._result(requests.post(url=f"{self.api_server}{resource}",
                                         json=params,
                                         timeout=self.timeout))

    def _build_intents(self, buy_token_address, sell_token_address):
        return [{
                "makerToken": buy_token_address,
                "takerToken": sell_token_address,
                "role": "maker"
            }, {
                "makerToken": sell_token_address,
                "takerToken": buy_token_address,
                "role": "maker"
            }]

    def _build_order(self,
                     maker_address,
                     maker_token,
                     maker_amount,
                     taker_address,
                     taker_token,
                     taker_amount):

        # Set 5-minute expiration on this order
        expiration = str(int(time.time()) + 300)
        nonce = random.randint(0, 99999)

        new_order = {
            "makerAddress": maker_address,
            "makerToken": maker_token,
            "makerAmount": maker_amount,
            "takerAddress": taker_address,
            "takerToken": taker_token,
            "takerAmount": taker_amount,
            "expiration": expiration,
            "nonce": nonce
        }

        return new_order
