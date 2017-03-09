FROM python:3.5.2

MAINTAINER Kamil Sokołowski <sokolowski.k@outlook.com.com>

RUN mkdir -p /app
ADD . /app

WORKDIR /app

EXPOSE 8080

RUN pip install -U pip && \
    pip install -r requirements.txt

CMD gunicorn wsgi:app --bind 0.0.0.0:8080 --worker-class aiohttp.worker.GunicornWebWorker
