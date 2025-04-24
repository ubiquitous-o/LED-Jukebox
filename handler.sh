#!/bin/bash
echo $PLAYER_EVENT
cd /usr/local/bin/led-jukebox
source venv/bin/activate
python main.py "$TRACK_ID" "$PLAYER_EVENT"