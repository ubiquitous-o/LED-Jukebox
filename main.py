import sys
import requests
from PIL import Image
import io
import base64
import json

from modules import spotify

def main():
    track_id = sys.argv[1] if len(sys.argv) > 1 else None
    event = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not track_id or not event:
        print("Usage: python main.py <track_id> <event>")
    
    # FlaskサーバーのURL
    flask_server_url = "http://localhost:5000/display"
    
    # JSONデータの初期化
    data = {"event": event}
    
    if event == "loading" or event == "track_changed":
        try:
            # Spotifyからアルバムアートを取得
            image_url = spotify.get_album_url(track_id)
            print(f"Fetching album art for track: {track_id}")
            
            # 画像をダウンロード
            img_response = requests.get(image_url, stream=True)
            img = Image.open(io.BytesIO(img_response.content))
            
            # 画像をリサイズ（必要に応じて）
            if img.size[0] != 64 or img.size[1] != 64:
                img = img.resize((64, 64), resample=Image.BICUBIC)
            
            # PILイメージをバイナリデータに変換
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Base64エンコード
            base64_image = base64.b64encode(img_byte_arr).decode('utf-8')
            
            # JSONデータに画像を追加
            data["image"] = base64_image
            
        except Exception as e:
            print(f"Error fetching album art: {e}")
    
    elif event == "stopped" or event == "paused":
        print("draw blackscreen")

    elif event == "session_connected":
        print("session connected")

    elif event == "session_disconnected":
        print("session disconnected")

    # FlaskサーバーにPOSTリクエストを送信
    try:
        response = requests.post(flask_server_url, json=data)
        print(f"Server response: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error sending data to server: {e}")   

if __name__ == "__main__":
    main()
