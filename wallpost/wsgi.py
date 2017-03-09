# -*- coding: utf-8 -*-
"""wsgi like"""

import os
import sys
import asyncio
import logging.config


SRC_ROOT = os.path.abspath(os.path.dirname(__file__))
sys.path.append(SRC_ROOT)


from app import create  # noqa


loop = asyncio.get_event_loop()
app = create(loop=loop)
