import datetime
import json
import os
import uuid

from fabric import api, operations, contrib
from fabric.state import env

from ulmg import do

import os

env.project_name = "ulmg"
env.user = "ubuntu"
env.forward_agent = True
env.branch = "main"

env.hosts = ["159.89.241.126"] # old

cd_string = "cd /home/ubuntu/apps/%(project_name)s; " % env
work_string = cd_string + "workon %(project_name)s && " % env

env.dbname = os.environ.get('PROD_PGDBNAME')
env.pgpass = os.environ.get('PROD_PGPASS')
env.pguser = os.environ.get('PROD_PGUSER')
env.pghost = os.environ.get('PROD_PGHOST')
env.pgport = os.environ.get('PROD_PGPORT')

env.admindbname = os.environ.get('PROD_ADMIN_PGDBNAME')
env.adminpguser = os.environ.get('PROD_ADMIN_PGUSER')
env.adminpgpass = os.environ.get('PROD_ADMIN_PGPASS')

# @api.task
# def development():
#     """
#     Work on development branch.
#     """
#     env.branch = "development"


# @api.task
# def branch(branch_name):
#     """
#     Work on any specified branch.
#     """
#     env.branch = branch_name


# @api.task
# def pull():
#     api.run(cd_string + "git fetch; git pull origin %(branch)s" % env)


# @api.task
# def pip_update():
#     api.run(work_string + "pip install --upgrade pip")


# @api.task
# def pip_install():
#     api.run(work_string + "pip install --upgrade -r requirements.txt")


# @api.task
# def migrate():
#     api.run(work_string + "django-admin migrate")


# @api.task
# def collectstatic():
#     api.run(work_string + "django-admin collectstatic --noinput")


# @api.task
# def bounce():
#     env.user = "root"
#     api.run("sudo service %(project_name)s stop" % env)
#     api.run("sudo service %(project_name)s start" % env)


# @api.task
# def mgmt(command):
#     cmd_string = "django-admin " + command
#     api.run(work_string + cmd_string)

@api.task
def get_dbshell():
    api.local(f"PGSSLMODE=require PGPASSWORD={env.adminpgpass} psql -U {env.adminpguser} -h {env.pghost} -p {env.pgport} -d {env.admindbname}")

@api.task
def get_data():
    # api.run("pg_dump -U ulmg -f /tmp/ulmg.sql -Fp -E UTF8 --inserts ulmg")
    # os.system("rm -rf data/sql/ulmg.sql")
    # api.get(remote_path="/tmp/ulmg.sql", local_path="data/sql/ulmg.sql")
    api.local(f"PGSSLMODE=require PGPASSWORD={env.pgpass} pg_dump -U {env.pguser} -h {env.pghost} -p {env.pgport} {env.dbname} > data/sql/{env.dbname}.sql")


@api.task
def reload():
    get_data()
    api.local("psql ulmg < data/sql/ulmg.sql")


@api.task
def get_app_data():
    apps = do.base_request(app="apps/63aa819a-ee7c-4cad-8b7b-2f979842e1ad")
    print(json.dumps(apps, indent=4, sort_keys=True))


# @api.task
# def deploy():
#     pull()
#     pip_install()
#     migrate()
#     collectstatic()
#     bounce()
