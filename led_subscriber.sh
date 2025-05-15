Xvfb :1 -screen 0 800x600x24 &
export DISPLAY=:1
sudo /usr/local/bin/LED-Jukebox/venv/bin/python /usr/local/bin/LED-Jukebox/led_subscriber.py