# pull official base image
FROM python:3.9.6-slim

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH "/usr/src/app/:/usr/src/app/config/:/usr/src/app/ulmg/"
ENV DJANGO_SETTINGS_MODULE="config.dev.settings"

# pyscopg2
RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt

# copy project
COPY . .