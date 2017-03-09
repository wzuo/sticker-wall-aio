# -*- coding: utf-8 -*-
import asyncio

from app.db import create_db


if __name__ == '__main__':
    print('Creating db')

    loop = asyncio.get_event_loop()
    create_db(loop)

    print('Done!')
