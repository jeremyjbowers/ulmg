#!/bin/bash

#
# Do not run this more than once
# very bad things will happen
# docker-compose down -v
# will remove the local volume
# so that you can re-run this script
#

createuser -U $POSTGRES_USER ubuntu
psql -U $POSTGRES_USER < /usr/src/app/data/sql/ulmg.sql
