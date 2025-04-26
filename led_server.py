from flask import Flask, request, jsonify
import base64
from PIL import Image
import io
import threading
import time
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import sys

app = Flask(__name__)

options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 5
options.brightness = 80
options.gpio_slowdown = 5
options.hardware_mapping = 'regular'

# options.show_refresh_rate = 1
options.limit_refresh_rate_hz = 60
framerate = 2 #30Hz animation in refresh_rate_hz = 60

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
    """バックグラウンドスレッドで画像をスクロール表示するための関数"""
    global stop_display, current_display
    
    if current_display is None:
        return
    
    # ダブルバッファリング用のキャンバスを作成
    double_buffer = matrix.CreateFrameCanvas()
    
    # 画像の幅と高さを取得
    img_width, img_height = current_display.size
    
    # スクロール位置の初期化
    xpos = 0
    
    # スクロール処理
    while not stop_display:
        # 位置を更新
        xpos = (xpos + 1) % img_width
        
        # ダブルバッファに画像を描画（スクロール位置を考慮）
        double_buffer.SetImage(current_display, -xpos)
        double_buffer.SetImage(current_display, -xpos + img_width)
        
        # バッファを入れ替えて表示を更新
        double_buffer = matrix.SwapOnVSync(double_buffer, framerate_fraction = framerate)

@app.route('/display', methods=['POST'])
def display_image():
    """画像データを受け取り、LEDマトリックスに表示するエンドポイント"""
    global current_display, display_thread, stop_display
    
    try:
        data = request.json
        
        # event情報を取得
        event = data.get('event')
        
        if event == "playing":
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
                display_thread.join(timeout=1.0)  # タイムアウト付きで待機
                
            # LEDマトリクスをクリア
            matrix.Clear()
            
            # 画像を保存
            current_display = concatenated_img.convert('RGB')
            
            # 表示維持用の新しいスレッドを開始
            stop_display = False
            display_thread = threading.Thread(target=display_image_loop)
            display_thread.daemon = True
            display_thread.start()
            
            return jsonify({"status": "success", "message": "Image displayed and scrolling"}), 200
            
        elif event == "stopped" or event == "paused":
            # スクロール停止
            if display_thread and display_thread.is_alive():
                stop_display = True
                display_thread.join(timeout=1.0)
            
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