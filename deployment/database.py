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


def upsert(session, model, values=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        for k,v in values.iteritems():
            setattr(instance, k, v)
    else:
        params = dict((k, v) for k, v in kwargs.iteritems())
        params.update(values or {})
        instance = model(**params)
        session.add(instance)
    return instance


def get_and_update(session, model, values=None, **kwargs):
    instance = session.query(model).filter_by(**kwargs).one_or_none()
    if instance is not None:
        for k,v in values.iteritems():
            setattr(instance, k, v)
    return instance


@contextmanager
def session_scope(expire_on_commit=False):
    """Provide a transactional scope around a series of operations."""
    session = Session(expire_on_commit=expire_on_commit)
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
