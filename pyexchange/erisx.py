# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019-2020 EdNoepel
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

import json
import jwt
import logging
import requests
import simplefix
import time
import uuid
import datetime

from dateutil import parser
from typing import List, Tuple

from pyexchange.api import PyexAPI
from pyexchange.fix import FixEngine
from pyexchange.model import Order, Trade
from pymaker.util import http_response_summary
from pymaker.numeric import Wad


class ErisxOrder(Order):

    @staticmethod
    def from_message(item: dict) -> Order:
        return Order(order_id=item['oid'],
                     timestamp=item['created_at'],
                     pair=item['book'],
                     is_sell=True if item['side'] == 'sell' else False,
                     price=Wad.from_number(item['price']),
                     amount=Wad.from_number(item['amount']))


class ErisxTrade(Trade):

    @staticmethod
    def from_message(trade: dict) -> Trade:
        if isinstance(trade['time'], int):
            timestamp = trade['time']
        else:
            timestamp = int(parser.isoparse(trade['time']).timestamp())

        return Trade(trade_id=trade['trade_id'],
                     timestamp=timestamp,
                     pair=trade["contract_symbol"].replace("/", "-"),
                     is_sell=True if trade['side'] == 'SELL' else False,
                     price=Wad.from_number(trade['px']),
                     amount=Wad.from_number(abs(float(trade['qty']))))


class ErisxApi(PyexAPI):
    """
    Implementation logic for interacting with the ErisX exchange, which uses FIX for order management and
    market data, and a WebAPI for retrieving account balances.

    ErisX documentation available here: https://www.erisx.com/wp-content/uploads/2020/03/ErisX-FIX-4.4-Spec-V3.3.pdf
    """

    logger = logging.getLogger()
    timeout = 5

    def __init__(self, fix_trading_endpoint: str, fix_trading_user: str,
                 fix_marketdata_endpoint: str, fix_marketdata_user: str, password: str,
                 clearing_url: str, api_key: str, api_secret: str, certs: str = None, account_id: int = 0):
        assert (isinstance(fix_trading_endpoint, str) or (fix_trading_endpoint is None))
        assert (isinstance(fix_trading_user, str) or (fix_trading_user is None))
        assert (isinstance(fix_marketdata_endpoint, str) or (fix_marketdata_endpoint is None))
        assert (isinstance(fix_marketdata_user, str) or (fix_marketdata_user is None))
        assert (isinstance(password, str) or (password is None))
        assert (isinstance(clearing_url, str) or (clearing_url is None))
        assert (isinstance(api_key, str) or (api_key is None))
        assert (isinstance(api_secret, str) or (api_secret is None))
        assert (isinstance(certs, str) or (certs is None))
        assert (isinstance(account_id, int))

        if certs is not None:
            certs = self._parse_cert_string(certs)

        # enable access from sync_trades and inventory_service without overriding socket
        if fix_trading_endpoint is not None and fix_trading_user is not None:
            self.fix_trading = ErisxFix(fix_trading_endpoint, fix_trading_user, fix_trading_user, password, certs)
            self.fix_trading.logon()
            self.fix_trading_user = fix_trading_user

        if fix_marketdata_endpoint is not None and fix_marketdata_user is not None:
            self.fix_marketdata = ErisxFix(fix_marketdata_endpoint, fix_marketdata_user, fix_marketdata_user, password,
                                           certs)
            self.fix_marketdata.logon()
            self.fix_marketdata_user = fix_marketdata_user

        self.clearing_url = clearing_url
        self.api_secret = api_secret
        self.api_key = api_key
        self.password = password

        # store the account id used to retrieve trades and balances
        self.account_id = self.get_account(account_id)

    def __del__(self):
        self.fix_marketdata.logout()
        self.fix_trading.logout()

    def reset_password(self, request_id: str, new_password: str):
        # Reset fix_marketdata
        m = self.fix_marketdata.create_message(simplefix.MSGTYPE_USER_REQUEST)

        m.append_pair(553, self.fix_marketdata_user)
        m.append_pair(554, self.password)
        m.append_pair(923, request_id)
        m.append_pair(924, 3)
        m.append_pair(925, new_password)

        self.fix_marketdata.write(m)

        # wait for response
        reset_market_data_password_response = self.fix_marketdata.wait_for_response('BF')
        if reset_market_data_password_response.get('926').decode('utf-8') != '5':
            self.logger.error(f"Unable to change password, message: {reset_market_data_password_response}")
        else:
            self.logger.info(f"Successfully reset marketdata password")

        # Reset fix_trading
        m = self.fix_trading.create_message(simplefix.MSGTYPE_USER_REQUEST)

        m.append_pair(553, self.fix_trading_user)
        m.append_pair(554, self.password)
        m.append_pair(923, request_id)
        m.append_pair(924, 3)
        m.append_pair(925, new_password)

        self.fix_trading.write(m)

        # wait for response
        reset_trading_password_response = self.fix_trading.wait_for_response('BF')
        if reset_trading_password_response.get('926').decode('utf-8') != '5':
            self.logger.error(f"Unable to change password, message: {reset_trading_password_response}")
        else:
            self.logger.info(f"Successfully reset trading password")

        # end session
        self.__del__()

    def ticker(self, pair):
        # TODO: Subscribe to L1 data, await receipt, and then unsubscribe and return the data.
        raise NotImplementedError()

    def get_markets(self):
        # Send 35=x, await 35=y
        message = self.fix_marketdata.create_message(simplefix.MSGTYPE_SECURITY_LIST_REQUEST)
        message.append_pair(320, 0)
        message.append_pair(559, 0)
        message.append_pair(simplefix.TAG_SYMBOL, 'NA')
        message.append_pair(460, 2)
        message.append_pair(1151, 'ALL')
        self.fix_marketdata.write(message)

        security_messages = []

        message = self.fix_marketdata.wait_for_response('y')
        security_messages.append(message)

        # continue waiting for the rest of the security list to arrive
        while message.get(893).decode('utf-8') != 'Y':
            message = self.fix_marketdata.wait_for_response('y')
            security_messages.append(message)

        return ErisxFix.parse_security_list(security_messages)

    # filter out the response from get markets
    def get_pair(self, pair: str) -> dict:
        return self.get_markets()[pair]

    def get_account(self, account_id: int) -> str:
        # Call into the /accounts method of ErisX Clearing WebAPI, and returns a string id used to identify the account.
        response = self._http_post("accounts", {})
        if "accounts" in response:
            return response["accounts"][account_id]["account_id"]
        else:
            raise RuntimeError("Couldn't interpret response")

    def get_balances(self):
        response = self._http_post("balances", {"account_id": self.account_id})
        if "balances" in response:
            return response["balances"]
        else:
            raise RuntimeError("Couldn't interpret response")

    # Order information is only retrieved on a per session basis (Page 20 of Spec)
    def get_orders(self, pair: str) -> List[Order]:
        assert (isinstance(pair, str))

        message = self.fix_trading.create_message(simplefix.MSGTYPE_ORDER_MASS_STATUS_REQUEST)
        message.append_pair(584, uuid.uuid4())
        message.append_pair(585, 8)

        self.fix_trading.write(message)
        unfiltered_orders = self.fix_trading.wait_for_get_orders_response()

        return list(map(lambda item: ErisxOrder.from_message(item), ErisxFix.parse_orders_list(unfiltered_orders)))

    def sync_orders(self, orders: List[Order]) -> List[Order]:
        """
        Sync keeper order state with erisx order state.
        If an order has been filled, it will be recorded as a trade on next trade sync.

        Only return a list of open orders.

        If an order has been partially filled,
        subtract the filled amount from the orders original amount.
        """
        assert (isinstance(orders, List))

        erisx_orders_state = self.fix_trading.sync_orders(orders)

        open_orders = []

        for order in orders:
            for erisx_order_state in erisx_orders_state:
                if order.order_id in erisx_order_state:
                    order.amount = order.amount - erisx_order_state[order.order_id]
                    open_orders.append(order)

        return open_orders

    def place_order(self, pair: str, is_sell: bool, price: float, amount: float) -> str:
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))
        assert (isinstance(price, float))
        assert (isinstance(amount, float))

        message = self.fix_trading.create_message(simplefix.MSGTYPE_NEW_ORDER_SINGLE)

        client_order_id = uuid.uuid4()
        side = 1 if is_sell is False else 2
        logging_side = 'Buy' if is_sell is False else 'Sell'
        base_currency = pair.split('/')[0]

        message.append_pair(simplefix.TAG_CLORDID, client_order_id)
        message.append_pair(simplefix.TAG_HANDLINST, simplefix.HANDLINST_AUTO_PRIVATE)
        message.append_pair(simplefix.TAG_CURRENCY, base_currency)
        message.append_pair(simplefix.TAG_SIDE, side)
        message.append_pair(simplefix.TAG_SYMBOL, pair)
        message.append_pair(460, 2)
        message.append_utc_timestamp(simplefix.TAG_TRANSACTTIME)
        message.append_pair(simplefix.TAG_ORDERQTY, amount)
        message.append_pair(simplefix.TAG_ORDTYPE, simplefix.ORDTYPE_LIMIT)  # always place limit orders
        message.append_pair(simplefix.TAG_PRICE, price)

        # place post only orders
        message.append_pair(simplefix.TAG_EXECINST, simplefix.EXECINST_PARTICIPATE_DONT_INITIATE)

        # Not yet supported - May be included in the future
        # message.append_pair(448, self.fix_trading_user)

        self.fix_trading.write(message)
        new_order = self.fix_trading.wait_for_order_processing_response('8', str(client_order_id))

        # Handle order rejections; ErisX will reject orders with 35=8, and 103=<X>
        # 103 codes are nonstandard. 100 is instrument closed, 23 is balance above limit.
        if new_order.get(simplefix.TAG_ORDERREJREASON) is not None:
            if new_order.get(simplefix.TAG_ORDERREJREASON) == b'100':
                self.logger.warning(f"Failed to place order as instrument is closed")
            elif new_order.get(simplefix.TAG_ORDERREJREASON) == b'23':
                self.logger.warning(f"Failed to place order as order would have exceeded balance limits")
            return ''

        erisx_oid = new_order.get(simplefix.TAG_ORDERID).decode('utf-8')
        client_oid = new_order.get(simplefix.TAG_CLORDID).decode('utf-8')
        order_id = f"{erisx_oid}|{client_oid}"

        self.logger.info(f"Placed {logging_side} order #{order_id} with amount {amount} at price of {price}")

        return order_id

    def cancel_order(self, order_id: str, pair: str, is_sell: bool) -> Tuple:
        """
            Send cancel order request to ErisX, and wait for the response.
            Returns a Tuple: [Cancellation_Status, Is_Unknown_Order]
        """
        assert (isinstance(order_id, str))
        assert (isinstance(pair, str))
        assert (isinstance(is_sell, bool))

        side = 1 if is_sell is False else 2
        erisx_oid = order_id.split('|')[0]
        client_oid = order_id.split('|')[1]
        message = self.fix_trading.create_message(simplefix.MSGTYPE_ORDER_CANCEL_REQUEST)

        message.append_pair(simplefix.TAG_CLORDID, uuid.uuid4())
        message.append_pair(simplefix.TAG_ORDERID, erisx_oid)
        message.append_pair(simplefix.TAG_ORIGCLORDID, client_oid)
        message.append_pair(simplefix.TAG_SYMBOL, pair)
        message.append_pair(simplefix.TAG_SIDE, side)
        message.append_utc_timestamp(simplefix.TAG_TRANSACTTIME)

        self.fix_trading.write(message)

        response = self.fix_trading.wait_for_order_processing_response('8', str(client_oid))

        if response.get(150) is not None:
            if response.get(150).decode('utf-8') == '4':
                # order cancelled successfully
                return True, False
            elif response.get(150).decode('utf-8') == 'F':
                # if an order has been filled before it can be cancelled,
                # treat it as an unknown order prompting the keeper to remove it from the client order book.
                self.logger.warning(f"Order was filled before it could be cancelled: {response.get(simplefix.TAG_ORDERID)}|{response.get(simplefix.TAG_CLORDID)}")
                return False, True
            else:
                self.logger.warning(f"Order not cancelled: {response.get(simplefix.TAG_ORDERID)}|{response.get(simplefix.TAG_CLORDID)}")
                return False, False
        else:
            if response.get(102).decode('utf-8') == '1':
                self.logger.warning(f"Order not found, cancellation failed for id: {response.get(simplefix.TAG_ORDERID)}|{response.get(simplefix.TAG_CLORDID)}")
                return False, True
            else:
                return False, False

    # Trade information is only retrieved on a per session basis through FIX (Page 20 of Spec)
    def get_trades(self, pair: str, page_number: int = 8) -> List[Trade]:
        response = self._http_post("trades", {"account_id": self.account_id})
        return list(map(lambda trade: ErisxTrade.from_message(trade), response["trades"]))

    # TODO: Not currently available
    def get_all_trades(self, pair, page_number) -> List[Trade]:
       pass

    def _http_get(self, resource: str, params=""):
        assert (isinstance(resource, str))
        assert (isinstance(params, str))

        if params:
            request = f"{resource}?{params}"
        else:
            request = resource

        return self._result(
            requests.get(url=f"{self.clearing_url}{request}",
                         headers=self._create_http_headers("GET", request, ""),
                         timeout=self.timeout))

    def _http_post(self, resource: str, params: dict):
        assert (isinstance(resource, str))
        assert (isinstance(params, dict))
        # Auth headers are required for all requests
        return self._result(
            requests.post(url=f"{self.clearing_url}{resource}",
                          data=params,
                          headers=self._create_http_headers("POST", resource),
                          timeout=self.timeout))

    def _create_http_headers(self, method, request_path):
        assert (method in ["GET", "POST"])
        assert (isinstance(request_path, str))

        unix_timestamp = int(round(time.time()))
        payload_dict = {'sub': self.api_key, 'iat': unix_timestamp}
        token = jwt.encode(payload_dict, self.api_secret, algorithm='HS256').decode('utf-8')

        headers = {
            "Authorization": f"Bearer {token}"
        }
        return headers

    @staticmethod
    def _result(response) -> dict:
        """Interprets the response to an HTTP GET or POST request"""
        if not response.ok:
            raise Exception(f"Error in HTTP response: {http_response_summary(response)}")
        else:
            return response.json()

    # Sync trades expects pair to be structured as <MAJOR>-<MINOR>, but Erisx expects <MAJOR>/<MINOR>
    @staticmethod
    def _format_pair_string(pair: str) -> str:
        assert (isinstance(pair, str))
        if '-' in pair:
            return "/".join(pair.split('-')).upper()
        else:
            return pair.upper()

    # convert key value pair into python dictionary
    @staticmethod
    def _parse_cert_string(certs: str) -> dict:
        parsed = {}
        for p in certs.split(","):
            var, val = p.split("=")
            parsed[var] = val
        return parsed

class ErisxFix(FixEngine):
    def __init__(self, endpoint: str, sender_comp_id: str, username: str, password: str, certs: dict = None):
        super(ErisxFix, self).__init__(endpoint=endpoint, sender_comp_id=sender_comp_id, target_comp_id="ERISX",
                                       username=username, password=password, certs=certs,
                                       fix_version="FIX.4.4", heartbeat_interval=10)

    @staticmethod
    def parse_security_list(messages: List[simplefix.FixMessage]) -> dict:
        assert (isinstance(messages, List))

        securities = {}

        for message in messages:
            security_count = int(message.get(146))
            for i in range(1, security_count + 1):

                # Required fields
                symbol = message.get(simplefix.TAG_SYMBOL, i).decode('utf-8')
                securities[symbol] = {
                    "Product": message.get(460, i).decode('utf-8'),
                    "MinPriceIncrement": float(message.get(969, i).decode('utf-8')),
                    "SecurityDesc": message.get(simplefix.TAG_SECURITYDESC, i).decode('utf-8'),
                    "Currency": message.get(simplefix.TAG_CURRENCY, i).decode('utf-8')
                }

                # Optional fields
                min_trade_vol = message.get(562, i)
                if min_trade_vol:
                    securities[symbol]["MinTradeVol"] = float(min_trade_vol.decode('utf-8'))
                max_trade_vol = message.get(1140, i)
                if max_trade_vol:
                    securities[symbol]["MaxTradeVol"] = float(max_trade_vol.decode('utf-8'))
                round_lot = message.get(561, i)
                if round_lot:
                    securities[symbol]["RoundLot"] = float(round_lot.decode('utf-8'))

        return securities

    @staticmethod
    def parse_orders_list(messages: simplefix.FixMessage) -> List:
        orders = []

        for message in messages:

            erisx_oid = message.get(simplefix.TAG_ORDERID).decode('utf-8')

            # Handle None response
            if erisx_oid == 'UNKNOWN':
                continue

            is_trade = message.get(simplefix.TAG_ORDSTATUS).decode('utf-8') == '2'

            # check to see order status is fully filled
            if is_trade:
                continue

            order_quantity = message.get(simplefix.TAG_ORDERQTY).decode('utf-8')

            side = 'buy' if message.get(simplefix.TAG_SIDE).decode('utf-8') == '1' else 'sell'
            order_id = f"{erisx_oid}|{message.get(simplefix.TAG_CLORDID).decode('utf-8')}"

            # Retrieve datetime and strip off nanoseconds
            created_at = message.get(simplefix.TAG_TRANSACTTIME).decode('utf-8')[:-3]
            timestamp = datetime.datetime.timestamp(datetime.datetime.strptime(created_at, '%Y%m%d-%H:%M:%S.%f'))
            # make timestamp an int with microseconds
            formatted_timestamp = int(timestamp * 1000000)

            order = {
                'side': side,
                'book': message.get(simplefix.TAG_SYMBOL).decode('utf-8'),
                'oid': order_id,
                'amount': order_quantity,
                'price': message.get(simplefix.TAG_PRICE).decode('utf-8'),
                'created_at': formatted_timestamp
            }
            orders.append(order)

        return orders
