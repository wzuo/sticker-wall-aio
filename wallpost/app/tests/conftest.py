# -*- coding: utf-8 -*-
import pytest
import aiopg
import asyncio
from datetime import datetime, timedelta
from aiohttp.test_utils import loop_context
from os import environ as env
from app import create
from app.db import create_table, user, token, sticker, ExtendedSAConnection
from aiopg.sa import create_engine


@pytest.fixture
def app(loop):
    return create(loop)


@pytest.yield_fixture
def loop():
    with loop_context() as loop:
        yield loop


@pytest.yield_fixture
def event_loop(loop):
    """
    This is needed for correct functioning of the test_client
    of aiohttp together with pytest.mark.asyncio pytest-asyncio decorator.
    For more info check the following link:
    https://github.com/KeepSafe/aiohttp/issues/939
    """
    loop._close = loop.close
    loop.close = lambda: None
    yield loop
    loop.close = loop._close


@pytest.fixture
def test_client_auth(
        loop, test_client, app, fixt_auth_header, fixt_db_user, fixt_db_token
):
    client_task = loop.run_until_complete(test_client(app))

    def auth_method(obj, method_name):
        """ Monkey-patch original method """
        new_method_name = 'original_%s' % method_name
        original_fun = getattr(obj, method_name)
        setattr(obj, new_method_name, original_fun)

        async def fun(url, **kwargs):
            kwargs.update(fixt_auth_header)

            new_fun = getattr(obj, new_method_name)
            return await new_fun(url, **kwargs)

        return fun

    client_task.get = auth_method(client_task, 'get')
    client_task.post = auth_method(client_task, 'post')
    client_task.delete = auth_method(client_task, 'delete')
    client_task.put = auth_method(client_task, 'put')
    yield client_task


@pytest.fixture
def test_client_no_auth(loop, test_client, app):
    client_task = loop.run_until_complete(test_client(app))
    yield client_task


@pytest.fixture
def make_sqlalchemy_connection(loop):
    conn = None

    async def go():
        nonlocal conn

        dsn = env.get('POSTGRESQL_URL')
        engine = await create_engine(dsn, loop=loop)
        await create_table(engine)

        conn = await engine.acquire()
        conn.__class__ = ExtendedSAConnection
        await conn.begin()
        return conn
    yield go

    if conn is not None:
        loop.run_until_complete(conn.close())


@pytest.fixture
def db_connection(loop, make_sqlalchemy_connection):
    conn = make_sqlalchemy_connection()
    resolved_conn = loop.run_until_complete(conn)
    yield resolved_conn

    if resolved_conn is not None:
        loop.run_until_complete(resolved_conn.rollback())
        loop.run_until_complete(resolved_conn.close())


@pytest.fixture
def fixt_auth_header():
    return {'headers': {'Authorization': 'Token TestToken'}}


@pytest.fixture
def fixt_wall_item():
    return {'title': 'Hi', 'description': 'Desc'}


@pytest.fixture
def fixt_user():
    return {'username': 'TestUserName', 'password': 'a'}


@pytest.fixture
def fixt_token(fixt_db_user):
    return {
        'user_id': fixt_db_user.id,
        'token': 'TestToken',
        'valid_until': datetime.utcnow() + timedelta(minutes=60),
    }


@pytest.fixture
def fixt_db_user(loop, fixt_user, db_connection):
    async def add():
        result = await db_connection.execute_fetchone(
            user.insert().values(**fixt_user))
        await db_connection.commit()

        fnd_user = await db_connection.execute_fetchone(
            user.select().where(user.c.id == result.id))
        return fnd_user

    return loop.run_until_complete(add())


@pytest.fixture
def fixt_db_token(loop, fixt_token, db_connection):
    async def add():
        result = await db_connection.execute_fetchone(
            token.insert().values(**fixt_token))
        await db_connection.commit()

        fnd_token = await db_connection.execute_fetchone(
            token.select().where(token.c.id == result.id))
        return fnd_token

    return loop.run_until_complete(add())


@pytest.fixture
def fixt_db_wall_item(loop, fixt_wall_item, db_connection):
    async def add():
        result = await db_connection.execute_fetchone(
            sticker.insert().values(**fixt_wall_item))
        await db_connection.commit()

        fnd_wall_item = await db_connection.execute_fetchone(
            sticker.select().where(sticker.c.id == result.id))
        return fnd_wall_item

    return loop.run_until_complete(add())


class Any(object):
    def __eq__(self, x):
        return True

    def __repr__(self):
        return 'Any'

    def __ne__(self, x):
        return not self.__eq__(x)


class AlmostSimilarDateTime(object):
    def __init__(self, expected, threshold=1):
        self.expected = expected
        self.threshold = threshold

    def __eq__(self, x):
        y = self.expected
        if isinstance(x, str):
            x = datetime.strptime(x, '%Y-%m-%dT%H:%M:%S.%f')

        if y < x:
            x, y = y, x
        return y - x < timedelta(seconds=self.threshold)

    def __repr__(self):
        return 'AlmostSimilarDateTime {}s {}'.format(
            self.threshold, self.expected)

    def __ne__(self, x):
        return not self.__eq__(x)
