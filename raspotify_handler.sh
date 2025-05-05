#!/bin/bash
echo $PLAYER_EVENT
echo $TRACK_ID

cd /usr/local/bin/LED-Jukebox
source venv/bin/activate
python track_publisher.py "$TRACK_ID" "$PLAYER_EVENT"