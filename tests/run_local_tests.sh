#/bin/bash
# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).

set -e
set -x
set +o pipefail

virtualenv venv

trap "rm -rf venv" EXIT

source ./venv/bin/activate

pip install -e '.[full]'

nosetests
