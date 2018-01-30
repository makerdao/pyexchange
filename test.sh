#!/bin/sh

PYTHONPATH=$PYTHONPATH:./lib/pymaker py.test --cov=pyexchange --cov-report=term --cov-append tests/
