import sys
import os
import time
from PIL import Image

# モジュール検索パスにプロジェクトのルートディレクトリを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# モジュールをインポート
from modules.led.led_matrix import LEDMatrix
from led_renderer import HeadlessCubeRenderer # クラス名を変更

def test_opengl_cube():
    """OpenGLキューブをLEDマトリックスに表示するテスト"""
    print("OpenGLキューブテストを開始します...")
    
    renderer = None 
    led_matrix_ctrl = None # matrix から led_matrix_ctrl に変更 (一貫性のため)

    try:
        # 1. OpenGLレンダラーの初期化
        print("HeadlessCubeRendererを初期化します...")
        # Xvfbなどの仮想ディスプレイが必要になる場合がある
        # export DISPLAY=:0 や Xvfb :0 -screen 0 64x64x24 & などを試す
        renderer = HeadlessCubeRenderer(width=64, height=64)
        print("HeadlessCubeRendererを初期化しました")

        # テスト用の画像を読み込む
        img_path = os.path.join(os.path.dirname(__file__), "album_test.jpg") # testディレクトリ内の画像を指定
        if not os.path.exists(img_path):
            print(f"警告: テスト画像が見つかりません: {img_path}。ダミー画像を使用します。")
            img = Image.new("RGB", (64, 64), "blue") # ダミー画像
        else:
            img = Image.open(img_path)
        
        if img.width != 64 or img.height != 64:
            img = img.resize((64, 64), Image.Resampling.LANCZOS)
        print("テスト画像の読み込み/準備が完了しました")
        
        # テクスチャを設定
        renderer.set_texture(img)
        print("テクスチャを設定しました")

        # 2. LEDマトリックスの初期化
        print("LEDマトリックスを初期化します...")
        led_matrix_obj = LEDMatrix() # LEDMatrix オブジェクトを作成
        led_matrix_ctrl = led_matrix_obj.matrix # matrix コントローラーを取得
        if led_matrix_ctrl is None:
            raise RuntimeError("LEDマトリックスの取得に失敗しました。rpi-rgb-led-matrixライブラリが正しくセットアップされているか確認してください。")
        print("LEDマトリックスを初期化しました")
        
        # 回転アニメーションを実行
        print("キューブの回転アニメーションを開始します...")
        
        # LEDパネルが5枚ある場合、キューブの異なる面を表示するなどの工夫が必要
        # ここでは、単純に同じ画像を5枚連結して表示する例を維持
        # 実際には、キューブの各面をレンダリングし、それらを配置する必要がある
        concat_width = 64 * 5 
        concat_height = 64
        
        for angle_deg in range(0, 360, 20): # 少しステップを大きく
            # キューブのレンダリング（異なる面を表示するには、カメラやモデルの向きを変える）
            # 例: 1枚目: 正面, 2枚目: 右面, ... など
            # ここでは単純に同じ回転でレンダリング
            renderer.render(angle_deg,0,0)
            cube_image_face = renderer.get_image() # キューブの現在のビューを取得
            
            if cube_image_face is None:
                print("警告: renderer.get_image() から None が返されました。")
                continue

            # 5つのLEDパネルに表示する画像を生成
            # TODO: ここでキューブの5つの異なる面をレンダリングし、配置するロジックが必要
            #       現在の実装では、同じ面を5つ並べているだけ
            # デバッグ用に最初のフレームを保存
            # if angle_deg == 100:
            #     try:
            #         cube_image_face.save("/tmp/debug_cube_face.png")
            #         print("デバッグ画像 debug_cube_face.png を保存しました。")
            #     except Exception as e_save:
            #         print(f"デバッグ画像の保存に失敗しました: {e_save}")

            concat_img = Image.new('RGB', (concat_width, concat_height))
            for i in range(5):
                # 異なる面を表示するには、ここで renderer.render() を異なるパラメータで呼び出し、
                # renderer.get_image() を再度呼び出す必要がある。
                # 例: renderer.render_face(i, angle_deg) のようなメソッドを renderer に追加する
                concat_img.paste(cube_image_face, (i * 64, 0)) 
            
            led_matrix_ctrl.SetImage(concat_img.convert("RGB")) # RGBに変換
            time.sleep(0.05)
            
        print("回転アニメーションが完了しました")
        
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