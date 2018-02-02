import datetime
import json
import os

from fabric import api, operations, contrib
from fabric.state import env

env.project_name = "ulmg"
env.user = "ubuntu"
env.forward_agent = True
env.branch = "master"

env.hosts = ["jeremybowers.com"]

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
    api.run("cd /home/ubuntu/apps/%(project_name)s; git fetch; git pull origin %(branch)s" % env)

@api.task
def pip_install():
    api.run("cd /home/ubuntu/apps/%(project_name)s; workon %(project_name)s && pip install -r requirements.txt" % env)

@api.task
def migrate():
    api.run("cd /home/ubuntu/apps/%(project_name)s; workon %(project_name)s && django-admin migrate" % env)

@api.task
def collectstatic():
    api.run("cd /home/ubuntu/apps/%(project_name)s; workon %(project_name)s && django-admin collectstatic --noinput" % env)

@api.task
def bounce(racedate=None):
    api.run("sudo service %(project_name)s stop" % env)
    api.run("sudo service %(project_name)s start" % env)

@api.task
def deploy():
    pull()
    pip_install()
    migrate()
    collectstatic()
    bounce()