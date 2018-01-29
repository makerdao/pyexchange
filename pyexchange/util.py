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

import errno
import hashlib
import os

import filelock
from appdirs import user_cache_dir
from tinydb import TinyDB, JSONStorage
from tinydb.middlewares import CachingMiddleware


def sort_trades(trades: list) -> list:
    return sorted(trades, key=lambda trade: trade.timestamp)


def filter_trades(trades: list, **kwargs) -> list:
    if 'from_timestamp' in kwargs:
        trades = list(filter(lambda trade: trade.timestamp >= kwargs['from_timestamp'], trades))

    if 'to_timestamp' in kwargs:
        trades = list(filter(lambda trade: trade.timestamp <= kwargs['to_timestamp'], trades))

    return trades


def get_db_file(exchange: str, server: str, key: str, role: str, pair: str):
    assert(isinstance(exchange, str))
    assert(isinstance(server, str))
    assert(isinstance(key, str))
    assert(isinstance(role, str))
    assert(isinstance(pair, str))

    db_folder = user_cache_dir("pyexchange", "maker")
    try:
        os.makedirs(db_folder)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    key = exchange + server + key + role + pair
    return os.path.join(db_folder, hashlib.sha1(bytes(key, 'utf-8')).hexdigest().lower() + ".hdb")


def get_lock(db_file: str):
    assert(isinstance(db_file, str))
    return filelock.FileLock(db_file + ".lock")


def get_db(db_file: str):
    assert(isinstance(db_file, str))
    return TinyDB(db_file, storage=CachingMiddleware(JSONStorage))

