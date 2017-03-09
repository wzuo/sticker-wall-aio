# -*- coding: utf-8 -*-
import os
import aiopg
from aiopg.sa import create_engine
import sqlalchemy as sa
from os import environ as env

from urllib import parse as urlparse
from aiohttp import web
from .app import (
    handle_list, handle_single, handle_create, handle_delete, handle_put,
    handle_login, handle_token
)
from .db import connect


async def connect_postgresql_db(app):
    dsn = app['config'].postgresql_dsn
    connection = await connect(dsn, loop=app.loop)
    app.db = connection
    return connection


async def disconnect_postgresql_db(app):
    app.db.close()


async def on_startup(app):
    await connect_postgresql_db(app)


async def on_shutdown(app):
    await disconnect_postgresql_db(app)


def setup_routers(app):
    app.router.add_post('/login', handle_login)
    app.router.add_post('/token', handle_token)

    app.router.add_get('/wall', handle_list)
    app.router.add_post('/wall', handle_create)
    app.router.add_get('/wall/{id}', handle_single)
    app.router.add_put('/wall/{id}', handle_put)
    app.router.add_delete('/wall/{id}', handle_delete)


class Base(object):
    @classmethod
    def setup(cls, app):
        app['config'] = cls

    postgresql_dsn = env.get('POSTGRESQL_URL', '')


class Main(Base):
    test = False


def create(loop, conf=None):
    if conf is None:
        conf = Main

    app = web.Application(loop=loop)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    conf.setup(app)
    setup_routers(app)

    return app
