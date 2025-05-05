#!/usr/bin/env python3
import paho.mqtt.client as mqtt
import json
import time
import signal
import sys
import logging
import socket
import os
import threading

from modules import config

# UNIXソケットパス
SOCKET_PATH = config.SOCKET_PATH

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MQTTDaemon:
    def __init__(self):
        self.running = True
        self.mqtt_client = None
        self.server_socket = None
        
    def setup_mqtt(self):
        """MQTTクライアントを設定して接続する"""
        try:
            # 新しいAPIバージョンを使用
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            
            # 接続時のコールバック
            def on_connect(client, userdata, flags, rc, properties=None):
                if rc == 0:
                    logger.info("Connected to MQTT broker")
                else:
                    logger.error(f"Failed to connect to MQTT broker with code: {rc}")
            
            client.on_connect = on_connect
            
            # ポート番号を整数型に変換して接続
            mqtt_port = int(config.MQTT_PORT) if isinstance(config.MQTT_PORT, str) else config.MQTT_PORT
            client.connect(config.MQTT_BROKER, mqtt_port, 60)
            client.loop_start()  # バックグラウンドでMQTT接続を維持
            
            self.mqtt_client = client
            logger.info("MQTT client setup complete")
            return True
        except Exception as e:
            logger.error(f"Error setting up MQTT client: {e}")
            return False
    
    def setup_socket(self):
        """UNIXソケットサーバーをセットアップする"""
        try:
            # 既存のソケットファイルを削除
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
                
            # UNIXソケットを作成
            self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(SOCKET_PATH)
            self.server_socket.listen(5)
            # ソケットファイルのパーミッション設定
            os.chmod(SOCKET_PATH, 0o777)
            logger.info(f"Socket server started at {SOCKET_PATH}")
            return True
        except Exception as e:
            logger.error(f"Error setting up socket server: {e}")
            return False
    
    def handle_client(self, client_socket):
        """クライアントからの接続を処理する"""
        try:
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            if data:
                msg_data = json.loads(data.decode('utf-8'))
                topic = msg_data.get('topic', f"{config.MQTT_TOPIC_BASE}/spotify")
                payload = msg_data.get('payload', {})
                
                # MQTTにメッセージを発行
                result = self.mqtt_client.publish(topic, json.dumps(payload))
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.info(f"Published message to topic {topic} successfully")
                else:
                    logger.error(f"Failed to publish message, error code: {result.rc}")
                    
        except Exception as e:
            logger.error(f"Error handling client connection: {e}")
        finally:
            client_socket.close()
    
    def run(self):
        """デーモンのメインループ"""
        # MQTTクライアントのセットアップ
        if not self.setup_mqtt():
            logger.error("Failed to setup MQTT client. Exiting.")
            return
        
        # ソケットサーバーのセットアップ
        if not self.setup_socket():
            logger.error("Failed to setup socket server. Exiting.")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            return
        
        # シグナルハンドラの設定
        def signal_handler(sig, frame):
            logger.info("Received signal to terminate.")
            self.running = False
            self.server_socket.close()
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            if os.path.exists(SOCKET_PATH):
                os.unlink(SOCKET_PATH)
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        logger.info("MQTT daemon is running...")
        
        # クライアント接続を処理
        while self.running:
            try:
                self.server_socket.settimeout(1.0)  # タイムアウトを設定してCtrl+Cに応答できるようにする
                try:
                    client_socket, _ = self.server_socket.accept()
                    client_thread = threading.Thread(target=self.handle_client, args=(client_socket,))
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:  # 終了処理中でなければエラーログを出力
                    logger.error(f"Error in main loop: {e}")
        
        # 終了処理
        logger.info("MQTT daemon is shutting down...")
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

if __name__ == "__main__":
    daemon = MQTTDaemon()
    daemon.run()