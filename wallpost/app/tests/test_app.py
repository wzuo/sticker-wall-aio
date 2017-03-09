# -*- coding: utf-8 -*-
import pytest
import json
from datetime import datetime, timedelta
from app.db import sticker, user, token
from app.app import safe_unpack
from app.tests.conftest import Any, AlmostSimilarDateTime


@pytest.mark.parametrize('data,count,expected', (
    (('a', 'b'), 2, ('a', 'b')),  # exact
    (('a', 'b', 'c'), 2, ('a', 'b')),  # too long input
    (('a',), 2, ('a', None)),  # too short input
    (('a',), 0, tuple()),  # zero wanted
    (tuple(), 0, tuple()),  # zero
    (tuple(), 2, (None, None)),  # two wanted but zero
))
def test_safe_unpack(data, count, expected):
    assert safe_unpack(data, count) == expected


async def test_create_sticker(db_connection):
    await db_connection.execute(
        sticker.insert().values(title='abc', description='def')
    )
    result = list(await db_connection.execute(sticker.select()))

    assert len(result) == 1
    assert result[0].title == 'abc'
    assert result[0].description == 'def'


async def test_create_user(db_connection):
    await db_connection.execute(
        user.insert().values(username='abc', password='def')
    )
    result = list(await db_connection.execute(user.select()))

    assert len(result) == 1
    assert result[0].username == 'abc'
    assert result[0].password == 'def'


async def test_create_token(db_connection, fixt_db_user):
    expected_datetime = datetime.utcnow()
    await db_connection.execute(token.insert().values(
        token='abc', valid_until=expected_datetime, user_id=fixt_db_user.id))
    result = list(await db_connection.execute(token.select()))

    assert len(result) == 1
    assert result[0].token == 'abc'
    assert result[0].valid_until == expected_datetime
    assert result[0].user_id == fixt_db_user.id


@pytest.mark.parametrize('prop,data', (
    ('username', {}),
    ('password', {'username': 'Test'}),
))
async def test_login_required_fields(test_client_no_auth, prop, data):
    resp = await test_client_no_auth.post('/login', data=json.dumps(data))

    assert resp.status == 400

    data = await resp.json()
    assert data == {'error': "'{}' is a required property".format(prop)}


async def test_login_not_existing(test_client_no_auth):
    resp = await test_client_no_auth.post('/login', data=json.dumps({
        'username': 'test',
        'password': 'test',
    }))

    assert resp.status == 404


async def test_login_returns_valid_token(
        test_client_no_auth, fixt_db_user, fixt_db_token
):
    resp = await test_client_no_auth.post('/login', data=json.dumps({
        'username': 'TestUserName',
        'password': 'a',
    }))

    assert resp.status == 200

    data = await resp.json()
    assert data == {
        'token': fixt_db_token.token,
        'valid_until': fixt_db_token.valid_until.isoformat(),
    }


async def test_login_creates_new_token(
        test_client_no_auth, fixt_db_user, db_connection
):
    resp = await test_client_no_auth.post('/login', data=json.dumps({
        'username': 'TestUserName',
        'password': 'a',
    }))

    assert resp.status == 200

    expected_datetime = AlmostSimilarDateTime(
        datetime.utcnow() + timedelta(minutes=60))
    data = await resp.json()
    assert data == {
        'token': Any(),
        'valid_until': expected_datetime
    }

    result = list(await db_connection.execute(token.select()))
    assert len(result) == 1
    assert result[0].token == data['token']
    assert result[0].valid_until == expected_datetime


async def test_token_required_fields(test_client_no_auth):
    resp = await test_client_no_auth.post('/token', data=json.dumps({}))

    assert resp.status == 400

    data = await resp.json()
    assert data == {'error': "'token' is a required property"}


async def test_token_bumps_token(test_client_no_auth, fixt_db_token):
    resp = await test_client_no_auth.post(
        '/token', data=json.dumps({'token': fixt_db_token.token}))

    assert resp.status == 200

    data = await resp.json()
    assert data == {
        'token': fixt_db_token.token,
        'valid_until': AlmostSimilarDateTime(
            datetime.utcnow() + timedelta(minutes=60))
    }


async def test_list_wall_empty(test_client_auth):
    resp = await test_client_auth.get('/wall')

    assert resp.status == 200

    data = await resp.json()
    assert data == []


async def test_list_wall(test_client_auth, db_connection, fixt_wall_item):
    await db_connection.execute(
        sticker.insert().values(**fixt_wall_item)
    )
    await db_connection.execute(
        sticker.insert().values(**fixt_wall_item)
    )
    await db_connection.commit()

    resp = await test_client_auth.get('/wall')

    assert resp.status == 200

    data = await resp.json()
    assert data == [
        {'id': Any(), **fixt_wall_item},
        {'id': Any(), **fixt_wall_item},
    ]


async def test_single_wall_not_found(test_client_auth, db_connection):
    resp = await test_client_auth.get('/wall/123')

    assert resp.status == 404


async def test_single_wall(test_client_auth, db_connection, fixt_wall_item):
    new_sticker = await db_connection.execute_fetchone(
        sticker.insert().values(**fixt_wall_item)
    )
    await db_connection.commit()

    resp = await test_client_auth.get('/wall/{}'.format(new_sticker.id))

    assert resp.status == 200

    data = await resp.json()
    assert data == {'id': new_sticker.id, **fixt_wall_item}


async def test_create_wall(test_client_auth, db_connection, fixt_wall_item):
    resp = await test_client_auth.post(
        '/wall', data=json.dumps(fixt_wall_item))

    assert resp.status == 201

    data = await resp.json()
    assert data == {'id': Any(), **fixt_wall_item}

    result = list(await db_connection.execute(sticker.select()))
    assert len(result) == 1
    assert result[0].title == 'Hi'
    assert result[0].description == 'Desc'


@pytest.mark.parametrize('prop,data', (
    ('title', {}),
    ('description', {'title': 'Test'}),
))
async def test_create_wall_invalid_data(
        test_client_auth, db_connection, prop, data
):
    resp = await test_client_auth.post(
        '/wall', data=json.dumps(data))

    assert resp.status == 400

    data = await resp.json()
    assert data == {'error': "'{}' is a required property".format(prop)}

    result = list(await db_connection.execute(sticker.select()))
    assert len(result) == 0


async def test_update_wall(
        test_client_auth, db_connection, fixt_wall_item, fixt_db_user
):
    new_sticker = await db_connection.execute_fetchone(
        sticker.insert().values(**fixt_wall_item)
    )
    await db_connection.commit()

    resp = await test_client_auth.put(
        '/wall/{}'.format(new_sticker.id), data=json.dumps(fixt_wall_item))

    assert resp.status == 201

    data = await resp.json()
    assert data == {'id': Any(), **fixt_wall_item}

    result = list(await db_connection.execute(sticker.select()))
    assert len(result) == 1
    assert result[0].title == 'Hi'
    assert result[0].description == 'Desc'


async def test_update_wall_not_existing(test_client_auth):
    resp = await test_client_auth.put('/wall/123', data=json.dumps({
        'title': 'a',
        'description': 'b',
    }))

    assert resp.status == 404


@pytest.mark.parametrize('prop,data', (
    ('title', {}),
    ('description', {'title': 'Test'}),
))
async def test_update_wall_invalid_data(
        test_client_auth, db_connection, prop, data, fixt_db_wall_item
):
    resp = await test_client_auth.put(
        '/wall/{}'.format(fixt_db_wall_item.id), data=json.dumps(data))

    assert resp.status == 400

    data = await resp.json()
    assert data == {'error': "'{}' is a required property".format(prop)}


async def test_delete_wall(test_client_auth, db_connection, fixt_wall_item):
    new_sticker = await db_connection.execute_fetchone(
        sticker.insert().values(**fixt_wall_item)
    )
    await db_connection.commit()

    resp = await test_client_auth.delete('/wall/{}'.format(new_sticker.id))

    assert resp.status == 204

    result = list(await db_connection.execute(sticker.select()))
    assert len(result) == 0


async def test_delete_wall_not_existing(test_client_auth, db_connection):
    resp = await test_client_auth.delete('/wall/123')

    assert resp.status == 404
