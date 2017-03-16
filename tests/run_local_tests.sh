#/bin/bash
# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).

set -e
set -x
set +o pipefail

virtualenv venv

trap "rm -rf venv" EXIT

source ./venv/bin/activate

# TODO: package the deployer
pip install gitpython=="0.3.2-rc1"

for dep in ws4py nose mock flask requests freezegun sqlalchemy enum34 bcrypt python-daemon cherrypy pyyaml marshmallow marshmallow-sqlalchemy bottle_sqlalchemy; do
    pip install "$dep"
done

nosetests
