import paho.mqtt.client as mqtt
import base64
from PIL import Image
import io
import threading
import time
import signal
import sys
import json
import logging
from rgbmatrix import RGBMatrix, RGBMatrixOptions

from modules import config
from modules.led.led_matrix import LEDMatrix
from modules.led.rotation import LEDRotationEffect, RotationAxis

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# RGBMatrix設定
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 5
options.brightness = 80
options.gpio_slowdown = 5
options.hardware_mapping = 'regular'
options.limit_refresh_rate_hz = 60
framerate = 2  # 30Hz animation in refresh_rate_hz = 60

try:
    # LEDマトリックスの初期化
    led_matrix = LEDMatrix()
    matrix = led_matrix.matrix
    
    # 回転エフェクト処理クラスの初期化
    rotation_effect = LEDRotationEffect(led_matrix)
    
    logger.info("LED Matrix and rotation effect initialized successfully")
except Exception as e:
    logger.error(f"Matrix initialization error: {e}")
    sys.exit(1)

# 現在表示中の画像を管理するための変数
current_display = None
original_image = None  # 回転エフェクトの元になる元画像
display_thread = None
stop_display = False
mqtt_client = None
rotation_lock = threading.Lock()  # 回転処理の排他制御用ロック

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
        double_buffer = matrix.SwapOnVSync(double_buffer, framerate_fraction=framerate)

def process_track_message(message_data):
    """トラック情報メッセージを処理する関数"""
    global current_display, original_image, display_thread, stop_display
    
    try:
        # event情報を取得
        event = message_data.get('event')
        logger.info(f"Processing track event: {event}")
        
        if event == "playing":
            # Base64エンコードされた画像データを取得
            image_data = message_data.get('image')
            if not image_data:
                logger.error("No image data provided")
                return
            
            # Base64デコード
            image_binary = base64.b64decode(image_data)
            
            # PILイメージに変換
            img = Image.open(io.BytesIO(image_binary))
            
            # 必要に応じてリサイズ
            if img.size[0] != 64 or img.size[1] != 64:
                img = img.resize((64, 64), resample=Image.BICUBIC)
            
            # オリジナル画像を保存（回転エフェクト用）
            original_image = img.copy()
            
            # 画像を横に5回連結
            concatenated_img = Image.new('RGB', (img.width * 6, img.height))
            for i in range(6):
                concatenated_img.paste(img, (i * img.width, 0))
            
            # # 以前の表示スレッドを停止
            # if display_thread and display_thread.is_alive():
            #     stop_display = True
            #     display_thread.join(timeout=1.0)  # タイムアウト付きで待機
                
            # LEDマトリクスをクリア
            matrix.Clear()
            
            # 画像を保存
            current_display = concatenated_img.convert('RGB')
            
            # # 表示維持用の新しいスレッドを開始
            # stop_display = False
            # display_thread = threading.Thread(target=display_image_loop)
            # display_thread.daemon = True
            # display_thread.start()
            
            # logger.info("Image displayed and scrolling")
            
        elif event == "stopped" or event == "paused":
            # # スクロール停止
            # if display_thread and display_thread.is_alive():
            #     stop_display = True
            #     display_thread.join(timeout=1.0)
            
            # マトリックスをクリア（黒画面表示）
            matrix.Clear()
            black_image = Image.new('RGB', (matrix.width, matrix.height), color=(0, 0, 0))
            matrix.SetImage(black_image)
            
            logger.info(f"Display {event}")
            
        else:
            logger.info(f"Event {event} acknowledged")
            
    except Exception as e:
        logger.error(f"Error processing track message: {e}")

def process_beat_message(message_data):
    """ビート検出メッセージを処理し、回転エフェクトを適用する関数"""
    global current_display, original_image
    
    try:
        # ロックを取得
        with rotation_lock:
            if not current_display or not original_image:
                logger.debug("No current image to apply rotation effect")
                return
                
            # ビート情報を取得
            beats = message_data.get('beats', {})
            
            # 各帯域のビート検出状態に応じて回転エフェクトを適用
            if beats.get('Bass'):
                logger.info("Bass beat detected, applying X axis rotation")
                current_display = rotation_effect.apply_rotation(
                    original_image,
                    current_display,
                    RotationAxis.X_INC,
                    max_angle=90,
                    angle_step=10
                )
                
            if beats.get('Mid'):
                logger.info("Mid beat detected, applying Y axis rotation")
                current_display = rotation_effect.apply_rotation(
                    original_image,
                    current_display,
                    RotationAxis.Y_INC,
                    max_angle=90,
                    angle_step=10
                )
                
            if beats.get('Treble'):
                logger.info("Treble beat detected, applying Z axis rotation")
                current_display = rotation_effect.apply_rotation(
                    original_image,
                    current_display,
                    RotationAxis.Z_INC,
                    max_angle=90,
                    angle_step=10
                )
                
    except Exception as e:
        logger.error(f"Error processing beat message: {e}")

def on_connect(client, userdata, flags, rc, properties=None):
    """MQTTブローカーに接続した際のコールバック"""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        
        # トラック情報トピックをサブスクライブ
        track_topic = f"{config.MQTT_TOPIC_BASE}/track"
        client.subscribe(track_topic)
        logger.info(f"Subscribed to topic: {track_topic}")
        
        # ビート情報トピックをサブスクライブ
        beat_topic = f"{config.MQTT_TOPIC_BASE}/beats"
        client.subscribe(beat_topic)
        logger.info(f"Subscribed to topic: {beat_topic}")
        
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_message(client, userdata, msg):
    """MQTTメッセージを受信した際のコールバック"""
    try:
        # JSONメッセージをデコード
        payload = msg.payload.decode('utf-8')
        message_data = json.loads(payload)
        logger.info(f"Received message on topic {msg.topic}")
        
        # トピックに応じて処理を分岐
        if msg.topic == f"{config.MQTT_TOPIC_BASE}/track":
            process_track_message(message_data)
        elif msg.topic == f"{config.MQTT_TOPIC_BASE}/beats":
            process_beat_message(message_data)
        else:
            logger.warning(f"Received message on unknown topic: {msg.topic}")
            
    except Exception as e:
        logger.error(f"Error in on_message callback: {e}")

def setup_mqtt_client():
    """MQTTクライアントを設定して接続する"""
    try:
        # 新しいAPIバージョンを使用
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        
        # コールバックを設定
        client.on_connect = on_connect
        client.on_message = on_message
        
        # ポート番号を整数型に変換して接続
        mqtt_port = int(config.MQTT_PORT) if isinstance(config.MQTT_PORT, str) else config.MQTT_PORT
        client.connect(config.MQTT_BROKER, mqtt_port, 60)
        
        return client
    except Exception as e:
        logger.error(f"Error setting up MQTT client: {e}")
        return None

def signal_handler(sig, frame):
    """シグナルハンドラ関数"""
    global stop_display, mqtt_client
    logger.info("Shutting down...")
    
    # 表示スレッドを停止
    stop_display = True
    
    # マトリックスをクリア
    matrix.Clear()
    
    # MQTTクライアントを停止
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    
    sys.exit(0)

def main():
    """メインエントリポイント"""
    global mqtt_client
    
    # シグナルハンドラをセットアップ
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # MQTTクライアントを初期化
    mqtt_client = setup_mqtt_client()
    if not mqtt_client:
        logger.error("Failed to setup MQTT client. Exiting.")
        return
    
    logger.info("Starting LED subscriber...")
    
    try:
        # メインループ開始
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        signal_handler(None, None)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        signal_handler(None, None)

if __name__ == '__main__':
    main()