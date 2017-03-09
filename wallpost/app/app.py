# -*- coding: utf-8 -*-
import json
import random
import string

from aiohttp import web
from datetime import datetime, timedelta
from functools import wraps
from jsonschema import validate, ValidationError
from sqlalchemy import select, and_
from .db import sticker, user, token, require_postgresql_conn
from .schemas import login_schema, refresh_token_schema, sticker_create_schema


def _dump_sticker(sticker):
    return {
        'id': sticker.id,
        'title': sticker.title,
        'description': sticker.description
    }


def _dump_login_token(token):
    return {
        'token': token.token,
        'valid_until': token.valid_until,
    }


def json_response(data, *args, **kwargs):
    def _serialize_data(data):
        if isinstance(data, list):
            return [_serialize_data(x) for x in data]
        elif not isinstance(data, dict):
            return data

        for k in data:
            v = data[k]
            if isinstance(v, datetime):
                data[k] = v.isoformat()
        return data
    return web.json_response(_serialize_data(data), *args, **kwargs)


def safe_unpack(data, wanted_count):
    if len(data) < wanted_count:
        return tuple(list(data) + [None] * (wanted_count - len(data)))

    return tuple(data[:wanted_count])


def require_auth_token(f):
    @wraps(f)
    async def fun(request, conn, *args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        method, data = safe_unpack(auth_header.split(' '), 2)
        if method != 'Token':
            return web.Response(status=401)

        fnd_user = list(await conn.execute(
            select([user]).select_from(
                user.join(token, token.c.user_id == user.c.id)
            ).where(and_(
                token.c.token == data,
                token.c.valid_until >= datetime.utcnow()))))
        if len(fnd_user) == 0:
            return web.Response(status=401)

        return await f(request, conn, *args, **kwargs, user=fnd_user[0])

    return fun


def validate_post_schema(schema):
    def decorator(f):
        @wraps(f)
        async def fun(request, *args, **kwargs):
            # assuming input is JSON
            try:
                data = await request.json()
            except json.JSONDecodeError:
                return web.Response(status=400)

            try:
                validate(data, schema)
            except ValidationError as e:
                return json_response({'error': e.message}, status=400)

            return await f(request, *args, **kwargs, data=data)

        return fun
    return decorator


@require_postgresql_conn
@validate_post_schema(login_schema)
async def handle_login(request, conn, data):
    def _gen_token():
        N = 30
        return ''.join(random.choice(
            string.ascii_letters + string.digits) for _ in range(N))

    async def _create_new_token(user_id):
        data = {
            'user_id': user_id,
            'token': _gen_token(),
            'valid_until': datetime.utcnow() + timedelta(minutes=60)
        }
        new_token = await conn.execute_fetchone(token.insert().values(**data))
        return await conn.execute_fetchone(
            token.select().where(token.c.id == new_token.id))

    async def _get_valid_token(user_id):
        return await conn.execute_fetchone(
            token.select().where(token.c.user_id == user_id))

    async def _find_user(username, password):
        return await conn.execute_fetchone(
            user.select().where(and_(
                user.c.username == username,
                user.c.password == password
            )))

    fnd_user = await _find_user(**data)
    if not fnd_user:
        return web.Response(status=404)

    fnd_token = await _get_valid_token(fnd_user.id)
    if not fnd_token:
        fnd_token = await _create_new_token(fnd_user.id)

    return json_response(_dump_login_token(fnd_token))


@require_postgresql_conn
@validate_post_schema(refresh_token_schema)
async def handle_token(request, conn, data):
    async def _get_valid_token(token_data):
        return await conn.execute_fetchone(
            token.select().where(token.c.token == token_data))

    async def _bump_token(fnd_token, valid_until):
        await conn.execute(token.update().where(
            token.c.id == fnd_token.id).values(valid_until=valid_until))

    fnd_token = await _get_valid_token(data['token'])
    await _bump_token(fnd_token, datetime.utcnow() + timedelta(minutes=60))

    fnd_token = await _get_valid_token(data['token'])
    return json_response(_dump_login_token(fnd_token))


@require_postgresql_conn
@require_auth_token
async def handle_list(request, conn, user):
    result = await conn.execute(sticker.select())
    return json_response([_dump_sticker(x) for x in result])


@require_postgresql_conn
@require_auth_token
async def handle_single(request, conn, user):
    id_ = request.match_info.get('id')
    result = await conn.execute_fetchone(
        sticker.select().where(sticker.c.id == id_))
    if result:
        return json_response(_dump_sticker(result))

    return web.Response(status=404)


@require_postgresql_conn
@require_auth_token
@validate_post_schema(sticker_create_schema)
async def handle_create(request, conn, user, data):
    new_sticker = await conn.execute_fetchone(
        sticker.insert().values(**data))

    new_sticker = await conn.execute_fetchone(
        sticker.select().where(sticker.c.id == new_sticker.id))

    return json_response(_dump_sticker(new_sticker), status=201)


@require_postgresql_conn
@require_auth_token
@validate_post_schema(sticker_create_schema)
async def handle_put(request, conn, user, data):
    id_ = request.match_info.get('id')
    new_sticker = await conn.execute_fetchone(
        sticker.select().where(sticker.c.id == id_))
    if not new_sticker:
        return web.Response(status=404)

    await conn.execute(sticker.update().where(
        sticker.c.id == new_sticker.id).values(**data))

    new_sticker = await conn.execute_fetchone(
        sticker.select().where(sticker.c.id == id_))
    return json_response(_dump_sticker(new_sticker), status=201)


@require_postgresql_conn
@require_auth_token
async def handle_delete(request, conn, user):
    id_ = request.match_info.get('id')
    x = await conn.execute(sticker.delete().where(sticker.c.id == id_))
    return web.Response(status=204 if x.rowcount else 404)
