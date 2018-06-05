# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
from contextlib import contextmanager
import threading

import sqlalchemy as sa
from sqlalchemy import orm

from . import schemas
from .samodels import Base

_engine = None


def engine():
    global _engine
    if _engine is None:
        raise ValueError("Engine not initialized yet, call init_db first")
    return _engine


Session = orm.sessionmaker()


_lock = threading.Lock()


def create_all():
    global _engine
    with _lock:
        if _engine is None:
            raise AssertionError('init_db must be called first')
    Base.metadata.create_all(_engine)


def drop_all():
    global _engine
    with _lock:
        if _engine is None:
            raise AssertionError('init_db must be called first')
    Base.metadata.drop_all(_engine)


# For use mainly in tests
def stop_engine():
    global _engine
    with _lock:
        if _engine is None:
            raise AssertionError('init_db must be called first')
        _engine.dispose()
        _engine = None


def init_db(connection_string):
    global _engine
    with _lock:
        if _engine is not None:
            raise AssertionError('init_db was already called')
        if connection_string.startswith('sqlite'):
            # SQLite does not support connection pools
            _engine = sa.create_engine(connection_string)
        else:
            _engine = sa.create_engine(connection_string, pool_recycle=3600, pool_size=20, max_overflow=50)
        Session.configure(bind=_engine)
        schemas.register_schemas(Base)


def get_or_create(session, model, defaults=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:

        params = dict((k, v) for k, v in kwargs.iteritems())
        if type(defaults) == model:
            defaults = model.__marshmallow__().dump(defaults).data
        params.update(defaults or {})
        instance = model(**params)
        session.add(instance)
        return instance, True


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
