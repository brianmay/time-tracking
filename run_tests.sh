#!/bin/sh
set -ex
isort -rc --check --diff process
flake8 process
mypy --strict --ignore-missing-imports process
