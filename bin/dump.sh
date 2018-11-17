#!/bin/bash
cd /home/ubuntu/apps/ulmg; sudo su -c workon ulmg && django-admin dumpdata ulmg > /tmp/ulmg.json