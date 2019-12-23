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
import dateutil.parser
import time
import requests
import json
from leverj_ordersigner import sign_order
from pprint import pformat
from pymaker import Contract, Address, Transact, Wad
from pymaker.util import http_response_summary, bytes_to_hexstring
from typing import Optional
from pymaker.sign import eth_sign, to_vrs
from web3 import Web3
from typing import Optional, List
import urllib.request


class Order:
    def __init__(self,
                 order_id: str,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):

        assert(isinstance(order_id, str))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.order_id = order_id
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    @property
    def sell_to_buy_price(self) -> Wad:
        return self.price

    @property
    def buy_to_sell_price(self) -> Wad:
        return self.price

    @property
    def remaining_buy_amount(self) -> Wad:
        return self.amount*self.price if self.is_sell else self.amount

    @property
    def remaining_sell_amount(self) -> Wad:
        return self.amount if self.is_sell else self.amount*self.price

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_list(item: list, pair: str):
        return Order(order_id=item['uuid'],
                     pair=pair,
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['quantity']))


class Trade:
    def __init__(self,
                 trade_id: Optional[id],
                 timestamp: int,
                 pair: str,
                 is_sell: bool,
                 price: Wad,
                 amount: Wad):
        assert(isinstance(trade_id, int) or (trade_id is None) or isinstance(trade_id, str))
        assert(isinstance(timestamp, int))
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        self.trade_id = trade_id
        self.timestamp = timestamp
        self.pair = pair
        self.is_sell = is_sell
        self.price = price
        self.amount = amount

    def __eq__(self, other):
        assert(isinstance(other, Trade))
        return self.trade_id == other.trade_id and \
               self.timestamp == other.timestamp and \
               self.pair == other.pair and \
               self.is_sell == other.is_sell and \
               self.price == other.price and \
               self.amount == other.amount

    def __hash__(self):
        return hash((self.trade_id,
                     self.timestamp,
                     self.pair,
                     self.is_sell,
                     self.price,
                     self.amount))

    def __repr__(self):
        return pformat(vars(self))

    @staticmethod
    def from_our_list(pair, trade):
        return Trade(trade_id=trade['executionid'],
                     timestamp=int(int(trade['eventTime'])/1000000),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['quantity']))

    @staticmethod
    def from_all_list(pair, trade):
        return Trade(trade_id=None,
                     timestamp=int(trade['date']),
                     pair=pair,
                     is_sell=True if trade['side'] == 'sell' else False,
                     price=Wad.from_number(trade['price']),
                     amount=Wad.from_number(trade['volume']))


class LeverjAPI(PyexAPI):
    """LeverJ API interface.
    """

    logger = logging.getLogger()

    def __init__(self, web3: Web3, api_server: str, account_id: str, api_key: str, api_secret: str, timeout: float):
        assert(isinstance(api_key, str))
        assert(isinstance(api_secret, str))
        assert(isinstance(account_id, str))

        url = api_server + "/api/v1/all/config"
        self.web3 = web3

        self.api_server = api_server
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.timeout = timeout
        self.config = requests.get(url).json()

        self.logger.info(f"LEVERJ: account id is {self.account_id} and web3.eth.default account is {self.web3.eth.defaultAccount}")

    def get_account(self):
        return self._http_authenticated("GET", "/api/v1", "/account", None)

    def get_balances(self):
        return self._http_authenticated("GET", "/api/v1", "/account/balance", None)

    def get_balance(self, coin: str):
        assert(isinstance(coin, str))
        balances = self.get_balances()
        for key in balances:
            if balances[key]['symbol'] == coin:
                return balances[key]['plasma']

    def get_available_balance(self, coin: str):
        assert(isinstance(coin, str))
        balances = self.get_balances()
        for key in balances:
            if balances[key]['symbol'] == coin:
                return balances[key]['available']

    def get_pending(self, coin: str):
        assert(isinstance(coin, str))
        balances = self.get_balances()
        for key in balances:
            if balances[key]['symbol'] == coin:
                return balances[key]['pending']

    def get_config(self):
        return self.config

    def get_spot_exchange_id(self):
        config = self.get_config()
        return config['config']['network']['appId']

    def get_custodian_address(self):
        config = self.get_config()
        return config['config']['network']['gluon']

    def get_product(self, pair: str):
        assert(isinstance(pair, str))
        return self.get_config()['instruments'][pair]

    def get_info(self):
        return self._http_authenticated("GET", "/api/v1", "/all/info", None)

    def get_all_orders(self):
        return self._http_authenticated("GET", "/api/v1", "/order", None)

    def get_orders(self, pair: str) -> List[Order]:
        assert(isinstance(pair, str))
        result_pair =  []
        result = self._http_authenticated("GET", "/api/v1", "/order", None)
        for item in result:
            if item['instrument'] == pair:
                result_pair.append(item)
        return list(map(lambda item: Order.from_list(item, pair), result_pair))

    def get_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        count = 200
        result_pair =  []
        result = self._http_authenticated("GET", "/api/v1", f"/account/execution?count={count}", None)
        for item in result:
            if item['instrument'] == pair:
                result_pair.append(item)

        return list(map(lambda item: Trade.from_our_list(pair, item), result_pair))

    def get_all_trades(self, pair: str, page_number: int = 1) -> List[Trade]:
        assert(isinstance(pair, str))
        assert(isinstance(page_number, int))
        result = self._http_authenticated("GET", "/api/v1", f"/instrument/{pair}/trade", None)

        return list(map(lambda item: Trade.from_all_list(pair, item), result))

    def get_symbol_trades(self, symbol: str):
        return self._http_authenticated("GET", "/api/v1", f"/instrument/{symbol}/trade", None)

    def get_orderbook_symbol(self, symbol: str):
        return self._http_authenticated("GET", "/api/v1", f"/instrument/{symbol}/orderbook", None)

    def createNewOrder(self, side: str, price: str, quantity: str, orderInstrument: dict) -> dict:
        precision = self.get_product(orderInstrument['symbol'])['quoteSignificantDigits']
        qty_precision = self.get_product(orderInstrument['symbol'])['baseSignificantDigits']
        order = {
                'orderType': 'LMT',
                'side': side,
                'price': round(float(price), precision),
                'quantity': round(float(quantity),qty_precision),
                'timestamp': int(time.time()*1000000),
                'accountId': self.account_id,
                'token': orderInstrument['quote']['address'],
                'instrument': orderInstrument['symbol']
                }
        order['signature'] = sign_order(order, orderInstrument, self.api_secret)
        return order

    def place_order(self, pair: str, is_sell: bool, price: Wad, amount: Wad):
        assert(isinstance(pair, str))
        assert(isinstance(is_sell, bool))
        assert(isinstance(price, Wad))
        assert(isinstance(amount, Wad))

        orderInstrument = self.get_product(pair)
        side = "sell" if is_sell else "buy"
        price = str(price)
        quantity = str(amount)
        order = self.createNewOrder(side, price, quantity, orderInstrument)
        self.logger.info(f'LEVERJ: order is {order}')
        return self._http_authenticated("POST", "/api/v1", "/order", [order])[0]['uuid']

    def cancel_order(self, order_id: str) -> bool:
        assert(isinstance(order_id, str))

        result = self._http_authenticated("DELETE", "/api/v1", f"/order/{order_id}", None)

        if order_id != result[0][0]:
            return False

        return True

    def cancel_all_orders(self) -> List:
        result = []

        orders = self.get_all_orders()

        for order in orders:
            order_id = order['uuid']
            result.append(self.cancel_order(order_id))

        return result

    def _http_authenticated(self, method: str, api_path: str, resource: str, body):
        assert(isinstance(method, str))
        assert(isinstance(api_path, str))
        assert(isinstance(resource, str))
        assert(isinstance(body, dict) or (body is None) or (body, list))

        data = json.dumps(body, separators=(',', ':'))
        nonce = int(time.time()*1000)

        params = {
            'method': method,
            'uri': resource,
            'nonce': nonce
            }


        if body is not None:
            params['body'] = body

        payload = str(nonce)
        signature = self._create_signature(payload)

        v, r, s = to_vrs(signature)

        auth_header = f"NONCE {self.account_id}.{self.api_key}"\
            f".{v}"\
            f".{bytes_to_hexstring(r)}"\
            f".{bytes_to_hexstring(s)}"

        headers={ "Authorization": auth_header, "Nonce": str(nonce) }
        if body is not None:
            headers["Content-Type"] = "application/json"

        return self._result(requests.request(method=method,
                                             url=f"{self.api_server}{api_path}{resource}",
                                             data=data,
                                             headers=headers,
                                             timeout=self.timeout))

    def _create_signature(self, params: str) -> str:
        assert(isinstance(params, str))

        return eth_sign(bytes(params, 'utf-8'), self.web3, self.api_secret, False, Address(self.account_id))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise Exception(f"Leverj API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except Exception:
            raise Exception(f"Leverj API invalid JSON response: {http_response_summary(result)}")

        return data

class LeverJ(Contract):
    """A client for the Leverj proxy exchange contract.

    Attributes:
        web3: An instance of `Web` from `web3.py`.
        address: Ethereum address of the `Leverj` custodian contract.
    """

    logger = logging.getLogger()

    abi = Contract._load_abi(__name__, 'abi/GLUON.abi')
    token_abi = Contract._load_abi(__name__, 'abi/ERC20TOKEN.abi')

    def __init__(self, web3: Web3, address: Address, middle_account: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(address, Address))
        assert(isinstance(middle_account, Address))

        self.web3 = web3
        self.address = address
        self.middle_account = middle_account
        self._contract = self._get_contract(web3, self.abi, address)

    def approve_token(self, token_address: str, amount: int) -> Transact:
        assert(isinstance(token_address, str))
        assert(isinstance(amount, int))

        token_contract = self._get_contract(self.web3, self.token_abi, Address(token_address))
        return Transact(self, self.web3, self.token_abi, Address(token_address), token_contract, "approve",[self.address.address, int(amount)], {}).transact(from_address=self.middle_account)

    def deposit_ether(self, leverjobj: LeverjAPI, amount: Wad, gluon_block_number):
        assert(isinstance(leverjobj, LeverjAPI))
        assert(isinstance(amount, Wad))

        custodian_account = self.address
        app_id = leverjobj.get_spot_exchange_id()
        if gluon_block_number is None:
            gluon_block_number = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}", None)['number'] + 2
            receipt = Transact(self, self.web3, self.abi, self.address, self._contract, "depositEther",[app_id], {'value': int(amount.value)}).transact(from_address=self.middle_account)
            return (gluon_block_number, receipt)
        else:
            current_gluon_block = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}", None)['number']
            if (current_gluon_block < gluon_block_number):
                return (gluon_block_number, None)
            else:
                return (None, None)

    def deposit_token(self,  leverjobj: LeverjAPI, token_address: str, amount: int, gluon_block_number):
        assert(isinstance(leverjobj, LeverjAPI))
        assert(isinstance(token_address, str))
        assert(isinstance(amount, int))

        custodian_account = self.address
        app_id = leverjobj.get_spot_exchange_id()
        if gluon_block_number is None:
            gluon_block_number = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}", None)['number'] + 2
            receipt = Transact(self, self.web3, self.abi, self.address, self._contract, "depositToken",[app_id, token_address, amount], {}).transact(from_address=self.middle_account)
            return (gluon_block_number, receipt)
        else:
            current_gluon_block = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}", None)['number']
            if (current_gluon_block < gluon_block_number):
                return (gluon_block_number, None)
            else:
                return (None, None)

    def post_pending_tx_hash(self, leverjobj: LeverjAPI, tx_hash: str, asset_addr: str, quantity: str):
        assert(isinstance(tx_hash, str))
        assert(isinstance(asset_addr, str))
        assert(isinstance(quantity, str))

        payload = {
                    "txid": tx_hash,
                    "asset": asset_addr,
                    "quantity": quantity
                  }
        balance_dict = leverjobj._http_authenticated("POST", "/api/v1", "/account/deposit", payload)
        return balance_dict

    def withdraw_token(self, leverjobj: LeverjAPI, token_addr: str, quantity: int) -> int:
        assert(isinstance(leverjobj, LeverjAPI))
        assert(isinstance(token_addr, str))
        assert(isinstance(quantity, int))

        app_id = leverjobj.get_spot_exchange_id()
        ethereum_account = leverjobj.account_id
        custodian_account = self.address
        timestamp = int(time.time()*1000)
        api_secret = leverjobj.api_secret
        sha3_hash =  Web3.soliditySha3(['string','string','uint256','uint256'],[ethereum_account, token_addr, int(quantity), timestamp])
        signature = eth_sign(sha3_hash, leverjobj.web3, api_secret, True, self.middle_account)
        payload = {
                    'asset': token_addr,
                    'quantity': str(int(quantity)),
                    'timestamp': timestamp,
                    'signature': signature
                  }
        leverjobj._http_authenticated("POST", "/api/v1", "/account/withdraw", payload)
        number_dict = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}", None)
        return number_dict['number']+3

    def claim_funds(self, leverjobj: LeverjAPI, asset: str, quantity: int, gluon_block_number):
        assert(isinstance(leverjobj, LeverjAPI))
        assert(isinstance(asset, str))
        assert(isinstance(quantity, int))

        app_id = leverjobj.get_spot_exchange_id()
        current_block = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}", None)['number']

        if gluon_block_number is None:
            return self.withdraw_token(leverjobj, asset, int(quantity))

        else:
            if current_block >= gluon_block_number:
                ethereum_account = leverjobj.account_id
                custodian_account = self.address
                self.logger.info(f"LEVERJ: ethereum_account: {ethereum_account}, custodian_account: {custodian_account}, asset: {asset}")
                response = leverjobj._http_authenticated("GET", "/api/v1", f"/plasma/{app_id}/evmparams/withdrawals/account/{ethereum_account}/asset/{asset}", None)
                response_app_id = int(response[0])
                response_bytes = response[1]
                self.logger.info(f"LEVERJ: finally gluon_block_number reached {gluon_block_number} and we are running final transact")
                Transact(self, self.web3, self.abi, self.address, self._contract, "withdraw",[response_app_id, response_bytes], {}).transact(from_address=self.middle_account)
                return None

        self.logger.info(f'LEVERJ: does not look like gluon_block_number reached {gluon_block_number} and we are currently at {current_block}')
        return gluon_block_number






