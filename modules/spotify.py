import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from modules import config

# returns an image url of the album cover
def get_album_url(track_id):
    auth_manager = SpotifyClientCredentials(client_id=config.SPOTIFY_CLIENT_ID,client_secret=config.SPOTIFY_SECRET_KEY)
    sp = spotipy.Spotify(auth_manager=auth_manager)

    # Get current playing
    track = sp.track(track_id)

    # Ensure that a track is playing
    if track is not None:
        # Get the album art
        return track['album']['images'][2]['url']
    else:
        return None

