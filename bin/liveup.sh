#!/bin/bash
# ABOUTME: Hourly loop for the ulmg-liveup worker. It refreshes MLB roster and stat data.
# ABOUTME: live_update is paused for the offseason; uncomment it to resume the hourly run.

while [ 1 ];
do
    # start time
    date +"%H:%M:%S"

    # Paused for the offseason. Uncomment to resume hourly roster and stat updates.
    # time django-admin live_update

    # end time
    date +"%H:%M:%S"

    sleep 3600
done
