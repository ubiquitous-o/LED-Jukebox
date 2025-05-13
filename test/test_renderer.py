import sys
import os
import time
from PIL import Image, ImageDraw
from PIL import ImageFont


# モジュール検索パスにプロジェクトのルートディレクトリを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# モジュールをインポート
from modules.led.led_matrix import LEDMatrix
from led_renderer import HeadlessCubeRenderer # クラス名を変更

def test_opengl_cube():
    """OpenGLキューブをLEDマトリックスに表示するテスト"""
    print("OpenGLキューブテストを開始します...")
    
    renderer = None 
    led_matrix_ctrl = None

    try:
        # 1. OpenGLレンダラーの初期化
        print("HeadlessCubeRendererを初期化します...")
        renderer = HeadlessCubeRenderer(
            width=64, 
            height=64, 
        )
        print("HeadlessCubeRendererを初期化しました")

        img = Image.new("RGB", (64, 64)) # テスト用に黒い画像を作成
        imgs = []
        for i in range(6):
            tmp = img.copy()
            background_colors = ["red", "green", "blue", "yellow", "purple", "orange"]
            tmp.paste(background_colors[i], [0, 0, tmp.width, tmp.height])
            draw = ImageDraw.Draw(tmp)
            text = str(i+1)
            font_size = 20  # 文字サイズを指定
            font = ImageFont.truetype("test/Courier.ttc", font_size)  # フォントを指定 (適切なフォントファイルを指定してください)
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_size = (text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1])
            text_position = ((tmp.width - text_size[0]) // 2, (tmp.height - text_size[1]) // 2)
            draw.text(text_position, text, fill="black", font=font)
            imgs.append(tmp)

        concat_img = Image.new("RGB", (img.width * 6, img.height))
        for i in range(6):
            concat_img.paste(imgs[i], (i * img.width, 0))
        # concat_img.save("test/concat_img.png") # 連結画像を保存 (デバッグ用)
        renderer.set_panorama_texture(concat_img) # 6面すべて同じ画像を使用
        print("テクスチャを設定しました")

        # 2. LEDマトリックスの初期化
        print("LEDマトリックスを初期化します...")
        led_matrix_obj = LEDMatrix()
        led_matrix_ctrl = led_matrix_obj.matrix
        if led_matrix_ctrl is None:
            raise RuntimeError("LEDマトリックスの取得に失敗しました。rpi-rgb-led-matrixライブラリが正しくセットアップされているか確認してください。")
        print("LEDマトリックスを初期化しました")
        
        print("アニメーションを開始します (キューブ全体を回転)...")
        for angle_deg in range(0, 360, 1): # 1周分、5度刻み
            
            
            stitched_face_images = renderer.render_cube_to_stitched_image(
                texture_rotation_axis=HeadlessCubeRenderer.ROTATION_AXIS_X,
                texture_rotation_angle_deg=angle_deg
            )
            filename = f"stitched_face_images_{angle_deg}.png"
            dirpath = os.path.join("output/" + filename)
            # stitched_face_images = stitched_face_images.crop((0, 0, stitched_face_images.width - img.width, stitched_face_images.height))
            stitched_face_images.save(dirpath)

            print(f"angle_deg: {angle_deg}")
            if stitched_face_images:
                led_matrix_ctrl.SetImage(stitched_face_images.convert("RGB"))
            else:
                print(f"警告: render_cube_to_stitched_image がNoneを返しました。")
            
            time.sleep(0.01)

        # for angle_deg in range(0, 360, 5): # 1周分、5度刻み

        #     # 連結された画像を取得 (面の順序を渡す必要がなくなる)
        #     stitched_face_images = renderer.render_cube_to_stitched_image(
        #         texture_effect_rot_x=0,
        #         texture_effect_rot_y=angle_deg, # Y軸回転のみ
        #         texture_effect_rot_z=0
        #     )
        #     if stitched_face_images:
        #         led_matrix_ctrl.SetImage(stitched_face_images.convert("RGB"))
        #     else:
        #         print(f"警告: render_cube_to_stitched_image がNoneを返しました。")
            
        #     time.sleep(0.01) 

        # for angle_deg in range(0, 360, 5): # 1周分、5度刻み

        #     # 連結された画像を取得 (面の順序を渡す必要がなくなる)
        #     stitched_face_images = renderer.render_cube_to_stitched_image(
        #         texture_effect_rot_x=0,
        #         texture_effect_rot_y=0, # Y軸回転のみ
        #         texture_effect_rot_z=angle_deg
        #     )
        #     if stitched_face_images:
        #         led_matrix_ctrl.SetImage(stitched_face_images.convert("RGB"))
        #     else:
        #         print(f"警告: render_cube_to_stitched_image がNoneを返しました。")
            
        #     time.sleep(0.01) 
        # print("アニメーションが完了しました")
        
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