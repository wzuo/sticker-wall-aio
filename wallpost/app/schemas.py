# -*- coding: utf-8 -*-
import jsonschema


login_schema = {
    'type': 'object',
    'properties': {
        'username': {'type': 'string'},
        'password': {'type': 'string'},
    },
    'required': ['username', 'password'],
}


refresh_token_schema = {
    'type': 'object',
    'properties': {
        'token': {'type': 'string'},
    },
    'required': ['token'],
}


sticker_create_schema = {
    'type': 'object',
    'properties': {
        'title': {'type': 'string'},
        'description': {'type': 'string'},
    },
    'required': ['title', 'description'],
}
