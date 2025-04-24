from flask import Flask, request, jsonify
import base64
from PIL import Image
import io
import threading
import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import sys

app = Flask(__name__)

# LEDマトリックスの設定
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 5
options.gpio_slowdown = 5
options.hardware_mapping = 'regular'  # Adafruit HATを使用している場合: 'adafruit-hat'

# マトリックスの初期化
try:
    matrix = RGBMatrix(options=options)
    print("LED Matrix initialized successfully")
except Exception as e:
    print(f"Matrix initialization error: {e}")
    sys.exit(1)

# 現在表示中の画像を管理するための変数
current_display = None
display_thread = None
stop_display = False

def display_image_loop():
    """バックグラウンドスレッドで画像表示を維持するための関数"""
    global stop_display
    while not stop_display:
        time.sleep(1)  # CPU使用率を下げるためのスリープ

@app.route('/display', methods=['POST'])
def display_image():
    """画像データを受け取り、LEDマトリックスに表示するエンドポイント"""
    global current_display, display_thread, stop_display
    
    try:
        data = request.json
        
        # event情報を取得
        event = data.get('event')
        
        if event == "loading" or event == "track_changed" or event == "playing":
            # Base64エンコードされた画像データを取得
            image_data = data.get('image')
            if not image_data:
                return jsonify({"error": "No image data provided"}), 400
            
            # Base64デコード
            image_binary = base64.b64decode(image_data)
            
            # PILイメージに変換
            img = Image.open(io.BytesIO(image_binary))
            
            # 必要に応じてリサイズ
            if img.size[0] != 64 or img.size[1] != 64:
                img = img.resize((64, 64), resample=Image.BICUBIC)
            
            # 画像を横に5回連結
            concatenated_img = Image.new('RGB', (img.width * 5, img.height))
            for i in range(5):
                concatenated_img.paste(img, (i * img.width, 0))
            
            # 以前の表示スレッドを停止
            if display_thread and display_thread.is_alive():
                stop_display = True
                display_thread.join()
                
            # LEDマトリックスをクリア
            matrix.Clear()
            
            # 新しい画像を表示
            matrix.SetImage(concatenated_img.convert('RGB'))
            current_display = concatenated_img
            
            # 表示維持用の新しいスレッドを開始
            stop_display = False
            display_thread = threading.Thread(target=display_image_loop)
            display_thread.daemon = True
            display_thread.start()
            
            return jsonify({"status": "success", "message": "Image displayed"}), 200
            
        elif event == "stopped" or event == "paused":
            # マトリックスをクリア（黒画面表示）
            matrix.Clear()
            black_image = Image.new('RGB', (matrix.width, matrix.height), color=(0, 0, 0))
            matrix.SetImage(black_image)
            
            return jsonify({"status": "success", "message": f"Display {event}"}), 200
            
        else:
            return jsonify({"status": "success", "message": f"Event {event} acknowledged"}), 200
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # サーバー起動
    app.run(host='0.0.0.0', port=5000, debug=False)