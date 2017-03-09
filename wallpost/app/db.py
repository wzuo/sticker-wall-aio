# -*- coding: utf-8 -*-
import aiopg
import asyncio
from aiopg.sa import create_engine, connection
from os import environ as env
from functools import wraps
import sqlalchemy as sa
from sqlalchemy.orm import relationship


metadata = sa.MetaData()

sticker = sa.Table(
    'sticker', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('title', sa.String(255), nullable=False),
    sa.Column('description', sa.Text),
)

user = sa.Table(
    'user', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('username', sa.String(255), nullable=False),
    sa.Column('password', sa.String(255), nullable=False),
)

token = sa.Table(
    'token', metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
    sa.Column('token', sa.String(255), nullable=False),
    sa.Column('valid_until', sa.DateTime, nullable=False),
    # relationship('user', back_populates='tokens')
)


async def create_table(engine):
    async with engine.acquire() as conn:
        await conn.execute('DROP TABLE IF EXISTS "token"')
        await conn.execute('DROP TABLE IF EXISTS "user"')
        await conn.execute('DROP TABLE IF EXISTS "sticker"')
        await conn.execute(
            '''CREATE TABLE sticker(
              id serial PRIMARY KEY,
              title varchar(255) not null,
              description text
            )'''
        )
        await conn.execute(
            '''CREATE TABLE "user"(
              id serial PRIMARY KEY,
              username varchar(255) not null,
              password varchar(255) not null
            )'''
        )
        await conn.execute(
            '''CREATE TABLE "token"(
              id serial PRIMARY KEY,
              user_id serial not null,
              token varchar(255) not null,
              valid_until timestamp not null,
              CONSTRAINT user_id_fk FOREIGN KEY(user_id) REFERENCES "user" (id)
            )'''
        )


async def connect_create_table(dsn, loop):
    engine = await connect(dsn, loop=loop)
    await create_table(engine)


async def connect(dsn, loop=None):
    conn = await create_engine(dsn, loop=loop)
    return conn


class ExtendedSAConnection(connection.SAConnection):
    async def execute_fetchone(self, query):
        result = await self.execute(query)
        return await result.fetchone()

    async def begin(self):
        return await self.execute('BEGIN')

    async def commit(self):
        return await self.execute('COMMIT')

    async def rollback(self):
        return await self.execute('ROLLBACK')


def require_postgresql_conn(f):
    @wraps(f)
    async def fun(request, *args, **kwargs):
        connection = request.app.db
        async with connection.acquire() as conn:
            conn.__class__ = ExtendedSAConnection
            return await f(request, *args, **kwargs, conn=conn)

    return fun


def create_db(loop):
    dsn = env.get('POSTGRESQL_URL')
    loop.run_until_complete(connect_create_table(dsn, loop))
