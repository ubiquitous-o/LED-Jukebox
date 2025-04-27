import sys
import os
# モジュール検索パスにプロジェクトのルートディレクトリを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from modules import spotify
from PIL import Image
import requests

def test_spotify():
    track_id = "5QMrH5nszZZR3nefIj6Mar"
    url = spotify.get_album_url(track_id)
    return url

if __name__ == "__main__":
    url = test_spotify()
    print(url)
    img = Image.open(requests.get(url, stream=True).raw)
    img.save("album_test.jpg")
