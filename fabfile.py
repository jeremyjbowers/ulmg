import datetime
import json
import os
import uuid

from fabric import api, operations, contrib
from fabric.state import env

env.project_name = "ulmg"
env.user = "ubuntu"
env.forward_agent = True
env.branch = "master"

# env.hosts = ["192.241.251.155"]
env.hosts = ["159.89.241.126"]

cd_string = "cd /home/ubuntu/apps/%(project_name)s; " % env
work_string = cd_string + "workon %(project_name)s && " % env

@api.task
def development():
    """
    Work on development branch.
    """
    env.branch = "development"

@api.task
def master():
    """
    Work on stable branch.
    """
    env.branch = "master"

@api.task
def branch(branch_name):
    """
    Work on any specified branch.
    """
    env.branch = branch_name

@api.task
def pull():
    api.run(cd_string + "git fetch; git pull origin %(branch)s" % env)

@api.task
def pip_install():
    api.run(work_string + "pip install --upgrade -r requirements.txt")

@api.task
def migrate():
    api.run(work_string + "django-admin migrate")

@api.task
def collectstatic():
    api.run(work_string + "django-admin collectstatic --noinput")

@api.task
def bounce():
    env.user = 'root'
    api.run("sudo service %(project_name)s stop" % env)
    api.run("sudo service %(project_name)s start" % env)

@api.task
def mgmt(command):
    cmd_string = "django-admin " + command
    api.run(work_string + cmd_string)

@api.task
def get_data():
    randid = "%s" % uuid.uuid1()
    api.run(work_string + "django-admin dumpdata ulmg > /tmp/ulmg-%s.json" % randid)
    os.system('rm -rf data/fixtures/ulmg.json')
    api.get(remote_path="/tmp/ulmg-%s.json" % randid, local_path="data/fixtures/ulmg.json")

@api.task
def reload():
    get_data()
    api.local('django-admin reload')

@api.task
def deploy():
    pull()
    pip_install()
    migrate()
    collectstatic()
    bounce()