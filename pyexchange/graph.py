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

import graphene
import requests
import json

from typing import List, Optional
from json import JSONDecodeError

from pymaker import Address
from lib.pymaker.pymaker.util import http_response_summary

get_our_trades_query = '''{
transactions(
    where: {
    timeStamp_gt: 1544832000
    timeStamp_lt: 1545696000
    tokenSymbol: "DAI"
    userAddress: "0x85c5c26dc2af5546341fc1988b9d178148b4838b"
  }
  first: 10)
  ) {
    id
  exchangeAddress
  userAddress
  block
  ethAmount
  tokenAmount
  fee
  event
  timeStamp
  }
})'''


get_markets_query = '''
{
  uniswap(id: "1") {
    exchangeCount
    totalVolumeInEth
    totalLiquidityInEth
    totalVolumeUSD
    totalLiquidityUSD
  }
}
'''

class Graph:

    def __init__(self, timeout: float = 9.5):
        assert (isinstance(timeout, float))

        self.timeout = timeout

    def http_request(self, resource: str = '', query: str = '') -> dict:
        assert (isinstance(resource, str))
        assert (isinstance(query, str))

        # data = json.dumps({'query': query}, separators=(',', ':'))
        data = query
        url = resource

        return self._result(requests.request(method="POST",
                                             url=url,
                                             data=data,
                                             timeout=self.timeout))

        # return self._result(requests.post(url, query))

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Graph API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except (RuntimeError, JSONDecodeError):
            raise ValueError(f"Graph API invalid JSON response: {http_response_summary(result)}")

        return data


graph_url = 'http://127.0.0.1:8000/subgraphs/name/davekaj/uniswap'
uniswap_graph = Graph()
print(uniswap_graph.http_request(graph_url, get_markets_query))
