import os
from dotenv import load_dotenv
load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET_KEY = os.getenv("SPOTIFY_SECRET_KEY")

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_BASE = "led-jukebox"
SOCKET_PATH = "/tmp/led_jukebox_mqtt.sock"