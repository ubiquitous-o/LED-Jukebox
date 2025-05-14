import sys
import os
import time
from PIL import Image, ImageDraw
from PIL import ImageFont

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.led_matrix import LEDMatrix

import importlib
led_jukebox_renderer = importlib.import_module("modules.LED-Jukebox-Visualizer.renderer.scroll_renderer")
import pyglet

def test_opengl_cube():
    """OpenGLキューブをLEDマトリックスに表示するテスト"""
    print("OpenGLキューブテストを開始します...")
    


    try:
        # 1. OpenGLレンダラーの初期化
        print("OpenGLレンダラーを初期化します...")
        renderer = led_jukebox_renderer.ScrollRenderer(64, 64, use_offscreen=True)
        print("OpenGLレンダラーを初期化しました")

        img = Image.new("RGBA", (64, 64))
        imgs = []
        background_colors = ["red", "green", "blue", "yellow", "purple", "orange"]
        for i in range(6):
            tmp = img.copy()
            tmp.paste(background_colors[i], [0, 0, tmp.width, tmp.height])
            draw = ImageDraw.Draw(tmp)
            text = str(i+1)
            font_size = 20
            font = ImageFont.truetype("test/Courier.ttc", font_size)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_size = (text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1])
            text_position = ((tmp.width - text_size[0]) // 2, (tmp.height - text_size[1]) // 2)
            draw.text(text_position, text, fill="black", font=font)
            imgs.append(tmp)

        concat_img = Image.new("RGBA", (img.width * 6, img.height))
        for i in range(6):
            concat_img.paste(imgs[i], (i * img.width, 0))
        
        renderer.set_panorama_texture(concat_img)

        # 2. LEDマトリックスの初期化
        print("LEDマトリックスを初期化します...")
        led_matrix_obj = LEDMatrix()
        led_matrix_ctrl = led_matrix_obj.matrix
        if led_matrix_ctrl is None:
            raise RuntimeError("LEDマトリックスの取得に失敗しました。rpi-rgb-led-matrixライブラリが正しくセットアップされているか確認してください。")
        print("LEDマトリックスを初期化しました")


        import time
        def update(dt):
            current_deg = (update.deg + 2) % 360
            renderer.rotate(led_jukebox_renderer.RotationAxis.X, -current_deg)
            renderer.on_draw()  # FBOに描画
            img = renderer.get_current_panorama_frame()  # FBOから画像取得
            if img:
                led_matrix_ctrl.SetImage(img.convert("RGB"))
            else:
                print(f"警告: get_current_panorama_frame がNoneを返しました。")
            update.deg = current_deg

            # save_path = f"out/rotated_image_{current_deg}.png"
            # img.save(save_path)

        update.deg = 0

        pyglet.clock.schedule_interval(update, 1/30)
        pyglet.app.run()
        
    except Exception as e:
        print(f"テスト実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # リソースをクリーンアップ
        if renderer:
            print("HeadlessCubeRendererをクリーンアップします...")
            renderer.cleanup()
        if led_matrix_ctrl: # led_matrix_ctrl をチェック
            print("LEDマトリックスをクリアします...")
            led_matrix_ctrl.Clear()
        print("テストが終了しました")

if __name__ == "__main__":
    # ヘッドレス環境でGLUTを実行するには、Xvfbなどの仮想Xサーバーが必要な場合があります。
    # 例:
    # $ Xvfb :1 -screen 0 800x600x24 &
    # $ export DISPLAY=:1
    # $ python test_renderer.py
    #
    # または、スクリプトの先頭で os.environ['DISPLAY'] = ':1' を設定することも検討できます。
    # (ただし、Xvfbの起動は別途必要)
    if 'DISPLAY' not in os.environ:
        print("警告: DISPLAY環境変数が設定されていません。ヘッドレス環境ではXvfbなどが必要になる場合があります。")
        os.environ['DISPLAY'] = ':1' # 必要に応じて設定

    test_opengl_cube()