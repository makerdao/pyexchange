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

import time
import logging
import requests

from typing import Optional
from json import JSONDecodeError
from lib.pyflex.pyflex.util import http_response_summary


class GraphClient:

    logger = logging.getLogger()

    def __init__(self, graph_url: str, timeout: float = 9.5):
        assert (isinstance(timeout, float))
        assert (isinstance(graph_url, str))

        self.graph_url = graph_url
        self.timeout = timeout

    def mutation_request(self, mutation: str, variables: dict = None):
        assert (isinstance(mutation, str))
        assert (isinstance(variables, dict) or isinstance(variables, None))

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        json = {'mutation': mutation}
        if variables:
            json['variables'] = variables

        result = self._result(requests.request(method="POST",
                                               url=self.graph_url,
                                               headers=headers,
                                               json=json,
                                               timeout=self.timeout))

        logging.info(f"Executed mutation and received response: {result}")
        return result['data']

    def query_request(self, query: str, variables: dict = None) -> dict:
        assert (isinstance(query, str))
        assert (isinstance(variables, str) or isinstance(variables, None))

        headers = {'Accept': 'application/json',
                   'Content-Type': 'application/json'}

        json = {'query': query}
        if variables:
            json['variables'] = variables

        result = self._result(requests.request(method="POST",
                                               url=self.graph_url,
                                               headers=headers,
                                               json=json,
                                               timeout=self.timeout))

        logging.info(f"Executed query and received response: {result}")
        return result['data']

    def _result(self, result) -> Optional[dict]:
        if not result.ok:
            raise RuntimeError(f"Graph API invalid HTTP response: {http_response_summary(result)}")

        try:
            data = result.json()
        except (RuntimeError, JSONDecodeError):
            raise ValueError(f"Graph API invalid JSON response: {http_response_summary(result)}")

        return data

