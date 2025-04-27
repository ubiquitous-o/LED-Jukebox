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
    result = Image.new('RGB', (img.width * 6, img.height))
    for i in range(6):
        result.paste(img, (i * img.width, 0))
    print("画像の連結が完了しました")
    
    try:
        led_matrix.matrix.SetImage(result)
        time.sleep(3)

        # 回転エフェクト実行（X軸正方向）
        print("X軸正方向の回転エフェクトを適用します...")
        result = rotation_effect.apply_rotation(
            img,
            result,
            RotationAxis.X_INC,
            max_angle=90,   # 90度まで回転
            angle_step=5    # 1度ずつ回転
        )

        # 回転エフェクト実行（X軸負方向）
        print("X軸負方向の回転エフェクトを適用します...")
        result = rotation_effect.apply_rotation(
            img,
            result,
            RotationAxis.X_DEC,
            max_angle=90,
            angle_step=5
        )

        # 回転エフェクト実行（Y軸正方向）
        print("Y軸正方向の回転エフェクトを適用します...")
        result = rotation_effect.apply_rotation(
            img, 
            result, 
            RotationAxis.Y_INC,
            max_angle=90,   # 45度まで回転
            angle_step=5    # 1度ずつ回転
        )
        
        # 回転エフェクト実行（Y軸負方向）
        print("Y軸負方向の回転エフェクトを適用します...")
        result = rotation_effect.apply_rotation(
            img, 
            result, 
            RotationAxis.Y_DEC,
            max_angle=90,
            angle_step=5
        )
        # 回転エフェクト実行（Z軸正方向）
        print("Z軸正方向の回転エフェクトを適用します...")
        result = rotation_effect.apply_rotation(
            img, 
            result, 
            RotationAxis.Z_INC,
            max_angle=90,   # 45度まで回転
            angle_step=5    # 1度ずつ回転
        )
        # 回転エフェクト実行（Z軸負方向）
        print("Z軸負方向の回転エフェクトを適用します...")
        result = rotation_effect.apply_rotation(
            img, 
            result, 
            RotationAxis.Z_DEC,
            max_angle=90,
            angle_step=5
        )
        
    
        print("すべての回転エフェクトが完了しました")
        
        # 最終結果を表示（少し表示を維持）
        led_matrix.matrix.SetImage(result)
        time.sleep(2)
        
    except Exception as e:
        print(f"エフェクト適用中にエラーが発生しました: {e}")
    finally:
        # クリーンアップ
        led_matrix.matrix.Clear()
        print("テストが終了しました")

if __name__ == "__main__":

    test_led_rotation()

