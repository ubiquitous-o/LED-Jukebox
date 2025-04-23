#!/bin/bash
if [ $PLAYER_EVENT = "playing" ] || [ $PLAYER_EVENT = "stopped" ] || [ $PLAYER_EVENT = "paused" ]; then
source /usr/local/bin/led-jukebox/venv/bin/activate
python /usr/local/bin/led-jukebox/main.py $TRACK_ID $PLAYER_EVENT
fi