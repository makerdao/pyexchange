#!/bin/sh

PYTHONPATH=$PYTHONPATH:./lib/pymaker py.test --cov=keeper --cov=pymaker --cov-report=term --cov-append tests/
