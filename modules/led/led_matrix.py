from rgbmatrix import RGBMatrix, RGBMatrixOptions
import sys

class LEDMatrix:
    def __init__(self):
        # LEDマトリックスの設定
        self.options = RGBMatrixOptions()
        self.options.rows = 64
        self.options.cols = 64
        self.options.chain_length = 5
        self.options.brightness = 100

        self.options.show_refresh_rate = 1
        self.options.limit_refresh_rate_hz = 60
        self.framerate = 2  # 30Hz animation in refresh_rate_hz = 60
        self.options.gpio_slowdown = 5
        self.options.hardware_mapping = 'regular'

        # マトリックスの初期化
        try:
            self.matrix = RGBMatrix(options=self.options)
            print("LED Matrix initialized successfully")
        except Exception as e:
            print(f"Matrix initialization error: {e}")
            sys.exit(1)

        # 現在表示中の画像を管理するための変数
        self.current_display = None
        self.display_thread = None
        self.stop_display = False