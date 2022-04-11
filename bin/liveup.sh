#!/bin/bash

while [ 1 ]; 
do
    # start time
    date +"%H:%M:%S"

    time django_admin live_update

    # end time
    date +"%H:%M:%S"

    sleep 600
done