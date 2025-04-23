#!/bin/bash
echo $PLAYER_EVENT
source /usr/local/bin/led-jukebox/venv/bin/activate
python /usr/local/bin/led-jukebox/main.py "$TRACK_ID" "$PLAYER_EVENT"