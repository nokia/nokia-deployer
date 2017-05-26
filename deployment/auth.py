# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import datetime
import uuid
import json
import bcrypt

from . import samodels as m


class AuthenticationError(Exception):
    pass


class InvalidSession(AuthenticationError):
    pass


class NoMatchingUser(AuthenticationError):
    pass


def issue_token(user, db):
    assert user is not None
    assert user.id is not None
    issued_at = datetime.datetime.utcnow()
    token = str(uuid.uuid4())
    user.token_issued_at = issued_at
    user.session_token = token
    db.commit()
    return json.dumps({
        'token': token,
        'expire_at': str(issued_at + datetime.timedelta(minutes=30)),
        'user': m.User.__marshmallow__().dump(user).data
    })


def check_hash(token, hashed):
    return bcrypt.hashpw(str(token), str(hashed)) == hashed


def hash_token(token, log_rounds=12):
    return bcrypt.hashpw(str(token), bcrypt.gensalt(log_rounds))
