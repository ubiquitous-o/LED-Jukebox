import sys
import time
import signal
import json
import socket
import logging
from datetime import datetime

from modules.audio_reactor import AudioReactor
from modules import config

# ロギング設定
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('beats_publisher')

# UNIXソケットパス
SOCKET_PATH = config.SOCKET_PATH

def send_mqtt_message(payload, topic=None):
    """UNIXソケット経由でMQTTデーモンにメッセージを送信する"""
    try:
        # UNIXソケットに接続
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(SOCKET_PATH)
        
        # トピックが指定されていなければデフォルト値を使用
        if not topic:
            topic = f"{config.MQTT_TOPIC_BASE}/beats"
        
        # メッセージを準備
        message = {
            "topic": topic,
            "payload": payload
        }
        
        # メッセージを送信
        client.sendall(json.dumps(message).encode('utf-8'))
        client.close()
        
        logger.debug(f"Message sent to MQTT daemon for topic: {topic}")
        return True
    except Exception as e:
        logger.error(f"Error sending message to MQTT daemon: {e}")
        return False

def main():
    """エントリーポイント"""
    running = True
    reactor = None
    
    # シグナルハンドラを設定
    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Received signal to terminate")
        running = False
        if reactor:
            reactor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # AudioReactorインスタンスを作成
    reactor = AudioReactor()
    if not reactor.start():
        logger.error("Failed to start AudioReactor")
        return 1
    
    logger.info("Beat detection started")
    
    try:
        while running:
            # オーディオチャンクを取得
            audio_chunk = reactor.get_audio_chunk()
            
            if audio_chunk is not None:
                # オーディオデータ取得のログ
                logger.debug(f"Processing audio chunk: {audio_chunk.shape}")
                
                # ビート検出
                detected_beats = reactor.detect_beats(audio_chunk)
                
                # ビートが検出されたらMQTTデーモンに送信
                if any(detected_beats.values()):
                    # 検出されたビートの詳細をログに記録
                    detected_bands = [band for band, detected in detected_beats.items() if detected]
                    logger.info(f"Beat detected in bands: {', '.join(detected_bands)}")
                    
                    # 現在のタイムスタンプを追加
                    payload = {
                        "timestamp": time.time(),
                        "beats": detected_beats
                    }
                    
                    # MQTTデーモンにメッセージを送信
                    success = send_mqtt_message(payload)
                    if success:
                        logger.debug("Beat message sent successfully")
                    else:
                        logger.warning("Failed to send beat message")
            
            else:
                # キューが空の場合は少し待つ
                logger.debug("No audio chunk available, waiting...")
                time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        # 終了処理
        if reactor:
            reactor.stop()
        logger.info("Beat detection stopped")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())