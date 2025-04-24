#!/bin/bash
echo $PLAYER_EVENT
echo $TRACK_ID

cd /usr/local/bin/led-jukebox
source venv/bin/activate
python main.py "$TRACK_ID" "$PLAYER_EVENT"