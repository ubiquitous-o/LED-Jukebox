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
import random
import os

from rgbmatrix import RGBMatrix, RGBMatrixOptions

from modules import config
from modules.led_matrix import LEDMatrix
# from modules.led.rotation import LEDRotationEffect, RotationAxis
import importlib
led_jukebox_renderer = importlib.import_module("modules.LED-Jukebox-Visualizer.renderer.scroll_renderer")
import pyglet

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    # LEDマトリックスの初期化
    led_matrix = LEDMatrix()
    matrix = led_matrix.matrix
    
    # 回転エフェクト処理クラスの初期化
    os.environ['DISPLAY'] = ':1' 
    renderer = led_jukebox_renderer.ScrollRenderer(64, 64, use_offscreen=True)
    
    logger.info("LED Matrix and rotation effect initialized successfully")
except Exception as e:
    logger.error(f"Matrix initialization error: {e}")
    sys.exit(1)

# 現在表示中の画像を管理するための変数
current_display = None
mqtt_client = None
rotation_lock = threading.Lock()  # 回転処理の排他制御用ロック

def process_track_message(message_data):
    """トラック情報メッセージを処理する関数"""
    global current_display
    
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
            
            # 画像を横に5回連結
            concatenated_img = Image.new('RGBA', (img.width * 6, img.height))
            for i in range(6):
                concatenated_img.paste(img, (i * img.width, 0))
            
            # LEDマトリクスをクリア
            matrix.Clear()
            
            renderer.set_panorama_texture(concatenated_img)
            renderer.on_draw()  # FBOに描画
            out_img = renderer.get_current_panorama_frame()
            if out_img:
                matrix.SetImage(out_img.convert("RGB"))
            else:
                logger.error("Failed to get current panorama frame")

            # 画像を保存
            current_display = concatenated_img.convert('RGB')
            

        # elif event == "paused":
        #     logger.info("Track paused")
        #     matrix.Clear()
        #     matrix.SetImage(current_display)

        elif event == "stopped":
            logger.info("Track stopped")
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
    global current_deg, target_deg
    try:
        with rotation_lock:
            beats = message_data.get('beats', {})
            if beats.get('Bass'):
                logger.info("Bass beat detected")
                axis = random.choice([led_jukebox_renderer.RotationAxis.X, led_jukebox_renderer.RotationAxis.Y, led_jukebox_renderer.RotationAxis.Z])
                direction random.choice([-1, 1])
                start_deg = 0
                end_deg = 90
                step = 5
                interval = 0.01
                deg = start_deg
                while deg < end_deg:
                    logger.debug(f"Rotating {axis} to {deg} degrees")
                    deg = min(deg + step, end_deg)
                    renderer.rotate(axis, deg * direction)
                    renderer.on_draw()
                    out_img = renderer.get_current_panorama_frame()
                    if out_img:
                        matrix.SetImage(out_img.convert("RGB"))
                    current_deg = deg
                    time.sleep(interval)

                current_display = out_img.convert('RGB')
                renderer.set_panorama_texture(current_display)
                renderer.on_draw()

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
    global mqtt_client
    logger.info("Shutting down...")
        
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