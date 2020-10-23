# pyexchange

Python API wrappers for some cryptocurrency exchanges.

<https://discord.gg/kB4vcYs>


## Getting Started
Run the following commands:
```
git submodule update --init --recursive
./install.sh
source _virtualenv/bin/activate
export PYTHONPATH=$PYTHONPATH:$PWD:$PWD/lib/pyflex
```

## Key facts

* This library depends on `pyflex` because some exchange APIs use the `Wad` class which is defined in `pyflex`.

* There is almost no test coverage as of today

* If you are looking for more supported exchanges and/or more features, a please have a look
  at `ccxt` (<https://github.com/ccxt/ccxt>). It's a JavaScript / Python / PHP library which
  supports huge number of venues and also has more features than `pyexchange`.

## License

See [COPYING](https://github.com/reflexer-labs/pyexchange/blob/master/COPYING) file.

### Testing
Run the following commands within a virtualenv
```
pip3 install -r requirements-dev.txt
./test.sh
```
