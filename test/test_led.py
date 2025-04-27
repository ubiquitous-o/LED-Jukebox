import sys
import os
import time
from PIL import Image

# モジュール検索パスにプロジェクトのルートディレクトリを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# LEDマトリックス関連のモジュールをインポート
from modules.led.led_matrix import LEDMatrix
from modules.led.rotation import LEDRotationEffect, RotationAxis

def test_led_rotation():
    """LEDマトリックスで回転エフェクトをテストする"""
    print("LEDマトリックスの回転エフェクトテストを開始します...")
    
    # LEDマトリックスの初期化
    led_matrix = LEDMatrix()
    
    # 回転エフェクト処理クラスの初期化
    rotation_effect = LEDRotationEffect(led_matrix)
    
    # テスト用の画像を読み込む
    try:
        img = Image.open("test/album_test.jpg")
        print("テスト画像の読み込みに成功しました")
    except Exception as e:
        print(f"画像読み込みエラー: {e}")
        sys.exit(1)
    
    # 画像のリサイズ
    if img.size[0] != 64 or img.size[1] != 64:
        img = img.resize((64, 64), resample=Image.BICUBIC)
        print("画像を64x64にリサイズしました")
    
    # LEDマトリックスをクリア
    led_matrix.matrix.Clear()
    
    # 連結画像を作成
    concatenated_img = Image.new('RGB', (img.width * 5, img.height))
    for i in range(5):
        concatenated_img.paste(img, (i * img.width, 0))
    print("画像の連結が完了しました")
    
    try:
        # 回転エフェクト実行（X軸正方向）
        print("Y軸正方向の回転エフェクトを適用します...")
        result1 = rotation_effect.apply_rotation(
            img, 
            concatenated_img, 
            RotationAxis.Y_INC,
            max_angle=90,   # 45度まで回転
            angle_step=1    # 1度ずつ回転
        )
        
        
        # 回転エフェクト実行（X軸負方向）
        print("Y軸負方向の回転エフェクトを適用します...")
        result2 = rotation_effect.apply_rotation(
            img, 
            result1, 
            RotationAxis.Y_DEC,
            max_angle=90,
            angle_step=1
        )
        
    
        print("すべての回転エフェクトが完了しました")
        
        # 最終結果を表示（少し表示を維持）
        led_matrix.matrix.SetImage(final_result)
        time.sleep(5)
        
    except Exception as e:
        print(f"エフェクト適用中にエラーが発生しました: {e}")
    finally:
        # クリーンアップ
        led_matrix.matrix.Clear()
        print("テストが終了しました")

def test_continuous_spin(duration=30):
    """連続的なスピン回転をテストする"""
    print(f"連続スピン回転テスト（{duration}秒）を開始します...")
    
    # LEDマトリックスの初期化
    led_matrix = LEDMatrix()
    
    # 回転エフェクト処理クラスの初期化
    rotation_effect = LEDRotationEffect(led_matrix)
    
    # テスト用の画像を読み込む
    img = Image.open("test/album_test.jpg")
    if img.size[0] != 64 or img.size[1] != 64:
        img = img.resize((64, 64), resample=Image.BICUBIC)
    
    # LEDマトリックスをクリア
    led_matrix.matrix.Clear()
    
    # ダブルバッファの作成
    canvas = led_matrix.matrix.CreateFrameCanvas()
    
    # 連結画像を作成
    concatenated_img = Image.new('RGB', (img.width * 5, img.height))
    for i in range(5):
        concatenated_img.paste(img, (i * img.width, 0))
    
    # 連続回転の開始
    start_time = time.time()
    angle = 0
    
    try:
        while time.time() - start_time < duration:
            # 角度を更新（連続的に）
            angle = (angle + 2) % 360
            
            # 回転した画像を生成
            rotated_img = img.rotate(angle, resample=Image.BICUBIC)
            
            # 画像を連結
            for i in range(5):
                concatenated_img.paste(rotated_img, (i * rotated_img.width, 0))
            
            # 表示
            canvas.SetImage(concatenated_img)
            canvas = led_matrix.matrix.SwapOnVSync(canvas)
            
            # 適切なフレームレート維持のために短時間スリープ
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("ユーザーによる中断")
    finally:
        # クリーンアップ
        led_matrix.matrix.Clear()
        print("連続スピン回転テストが終了しました")

if __name__ == "__main__":

    test_led_rotation()

