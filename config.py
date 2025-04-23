import os
from dotenv import load_dotenv
load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_SECRET_KEY = os.getenv("SPOTIFY_SECRET_KEY")