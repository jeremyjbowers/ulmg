#!/bin/bash
sudo su ubuntu && workon ulmg && django-admin dumpdata ulmg > /tmp/ulmg.json

