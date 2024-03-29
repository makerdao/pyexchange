# pyexchange

Python API wrappers for some cryptocurrency exchanges.

![Build Status](https://github.com/makerdao/petrometer/actions/workflows/.github/workflows/tests.yaml/badge.svg?branch=master)

<https://chat.makerdao.com/channel/keeper>


## Getting Started
Run the following commands:
```
git submodule update --init --recursive
source _virtualenv/bin/activate
bash ./install.sh
export PYTHONPATH=$PYTHONPATH:$PWD:$PWD/lib/pymaker
```

## Key facts

* These API wrappers expose only those endpoints which were necessary to implement
  `market-maker-keeper` (<https://github.com/makerdao/market-maker-keeper>), `market-maker-stats`
  (<https://github.com/makerdao/market-maker-stats>) and `sync-trades`.
  Due to it they cover most only order placement, order cancellation, reading balances and open orders,
  and retrieving past trade history.

* This library depends on `pymaker` because IDEX integration involves interacting with its smart contract.
  In addition to that, other exchange APIs use the `Wad` class which is defined `pymaker`.

* There is almost no test coverage as of today. The exception is some part of the IDEX API.

* If you are looking for more supported exchanges and/or more features, a please have a look
  at `ccxt` (<https://github.com/ccxt/ccxt>). It's a JavaScript / Python / PHP library which
  supports huge number of venues and also has more features than `pyexchange`.


## License

See [COPYING](https://github.com/makerdao/pyexchange/blob/master/COPYING) file.

### Testing
Run the following commands within a virtualenv
```
pip3 install -r requirements-dev.txt
./test.sh
```
