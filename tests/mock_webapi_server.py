# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 EdNoepel
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
import os


# Models HTTP response, produced by OkexMockServer
class MockedResponse:
    def __init__(self, text: str, status_code=200):
        assert (isinstance(text, str))
        assert (isinstance(status_code, int))
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.text = text
        self.reason = None

    def json(self, **kwargs):
        return json.loads(self.text)


# Determines response to provide based on the requested URL
class MockWebAPIServer:
    def __init__(self, response_file: str):
        """Read JSON responses from a pipe-delimited file, avoiding JSON-inside-JSON parsing complexities"""
        assert isinstance(response_file, str)

        self.responses = {}
        cwd = os.path.dirname(os.path.realpath(__file__))
        response_file_path = os.path.join(cwd, response_file)

        with open(response_file_path, 'r') as file:
            for line in file:
                kvp = line.split("|")
                assert (len(kvp) == 2)
                self.responses[kvp[0]] = kvp[1]

    def handle_request(self, **kwargs):
        assert("url" in kwargs)
        url = kwargs["url"]
        if "data" not in kwargs:
            return self.handle_get(url)
        else:
            return self.handle_post(url, kwargs["data"])

    def handle_get(self, url: str):
        """Override this to choose the appropriate response for the get request"""
        raise NotImplementedError()

    def handle_post(self, url: str, data):
        """Override this to choose the appropriate response for the post request"""
        raise NotImplementedError()
