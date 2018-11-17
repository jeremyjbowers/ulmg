#!/bin/bash
cd /home/ubuntu/apps/ulmg; sudo su -c "source ~/.bashrc && workon ulmg && django-admin dumpdata ulmg > /tmp/ulmg.json" ubuntu