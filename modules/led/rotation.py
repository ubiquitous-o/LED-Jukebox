from enum import Enum
from PIL import Image
import time
from modules.led.led_matrix import LEDMatrix

class RotationAxis(Enum):
    X_INC = 1  # X軸正方向
    X_DEC = 2  # X軸負方向
    Y_INC = 3  # Y軸正方向
    Y_DEC = 4  # Y軸負方向
    Z_INC = 5  # Z軸正方向
    Z_DEC = 6  # Z軸負方向

class LEDRotationEffect:
    def __init__(self, led_matrix):
        """
        回転効果を処理するクラス
        
        Args:
            led_matrix (LEDMatrix): 初期化済みのLEDMatrixインスタンス
        """
        self.led_matrix = led_matrix
        self.matrix = led_matrix.matrix
        self.framerate = led_matrix.framerate
    
    def apply_rotation(self, img, concat_img, rotation_axis, max_angle=90, angle_step=1):
        """
        画像に回転効果を適用する
        
        Args:
            img (PIL.Image): 元の画像
            concat_img (PIL.Image): 連結された画像
            rotation_axis (RotationAxis): 回転軸
            max_angle (int): 最大回転角度
            angle_step (int): 各ステップでの角度増分
            
        Returns:
            PIL.Image: 回転効果適用後の最終画像
        """
        angle = 0
        # ダブルバッファリング用のキャンバスを作成
        double_buffer = self.matrix.CreateFrameCanvas()
        scroll_img, rotate_img = self._get_rotation_img_vals(concat_img, img, rotation_axis)

        # 回転処理
        while not self.led_matrix.stop_display and angle <= max_angle:
            # キャンバスをクリア
            double_buffer.Clear()
            
            # 現在の角度と次の角度での画像を生成
            current_img = self._rotate_cube(img, scroll_img, rotate_img, angle, rotation_axis)
            next_img = self._rotate_cube(img, scroll_img, rotate_img, angle + 1, rotation_axis)
            
            # 画像を表示
            double_buffer.SetImage(current_img)
            double_buffer.SetImage(next_img)
            
            # バッファを入れ替えて表示を更新
            double_buffer = self.matrix.SwapOnVSync(
                double_buffer, 
                framerate_fraction=self.framerate
            )
            
            # 角度を更新
            angle += angle_step
        
        return current_img

    def _get_rotation_img_vals(self, concat_img, image, rotation_axis):
        """回転用の画像値を取得する"""
        if rotation_axis in [RotationAxis.X_INC, RotationAxis.X_DEC]:
            scroll_img = concat_img.crop((image.width, 0, concat_img.width, concat_img.height))
            rotate_img = concat_img.crop((0, 0, image.width, image.height))
            return scroll_img, rotate_img
        elif rotation_axis in [RotationAxis.Y_INC, RotationAxis.Y_DEC]:
            scroll_img = concat_img.crop((image.width, 0, concat_img.width, concat_img.height))
            rotate_img = concat_img.crop((0, 0, image.width, image.height))
            return scroll_img, rotate_img
        else:
            print(f"サポートされていない回転軸: {rotation_axis}")
            return None, None

    def _rotate_cube(self, image, scroll_img, rotate_img, angle, rotation_axis):
        """指定された軸に沿って画像を回転させる"""
        final_render = Image.new('RGB', (image.width * 5, image.height))
        
        if rotation_axis == RotationAxis.Y_INC:
            concatenated_img = Image.new('RGB', (image.width * 4, image.height))
            
            offset = int((angle / 360) * scroll_img.width)
            cropped_img = scroll_img.crop((offset, 0, scroll_img.width, scroll_img.height))
            ofsseted_img = scroll_img.crop((0, 0, offset, scroll_img.height))
            concatenated_img.paste(cropped_img, (0, 0))
            concatenated_img.paste(ofsseted_img, (cropped_img.width, 0))

            rotated_img = rotate_img.rotate(-angle, resample=Image.BICUBIC)
            final_render.paste(rotated_img, (0, 0))
            final_render.paste(concatenated_img, (rotated_img.width, 0))
            return final_render

        elif rotation_axis == RotationAxis.Y_DEC:
            concatenated_img = Image.new('RGB', (image.width * 4, image.height))
            
            offset = int((angle / 360) * scroll_img.width)
            cropped_img = scroll_img.crop((scroll_img.width - offset, 0, scroll_img.width, scroll_img.height))
            ofsseted_img = scroll_img.crop((0, 0, scroll_img.width - offset, scroll_img.height))
            concatenated_img.paste(cropped_img, (0, 0))
            concatenated_img.paste(ofsseted_img, (cropped_img.width, 0))

            rotated_img = rotate_img.rotate(angle, resample=Image.BICUBIC)
            final_render.paste(rotated_img, (0, 0))
            final_render.paste(concatenated_img, (rotated_img.width, 0))
            return final_render
            

            
        else:
            print(f"サポートされていない回転軸: {rotation_axis}")
            return Image.new('RGB', (image.width * 5, image.height), color=(0, 0, 0))


def create_rotation_effect(image_path, rotation_type=RotationAxis.Y_INC):
    """回転効果を作成して表示する"""
    # LEDMatrixの初期化
    led_matrix = LEDMatrix()
    
    # 回転エフェクトの初期化
    rotation_effect = LEDRotationEffect(led_matrix)
    
    # 画像の読み込み
    img = Image.open(image_path)
    if img.size[0] != 64 or img.size[1] != 64:
        img = img.resize((64, 64), resample=Image.BICUBIC)
    
    # 画像の連結
    concatenated_img = Image.new('RGB', (img.width * 5, img.height))
    for i in range(5):
        concatenated_img.paste(img, (i * img.width, 0))
    
    # 回転効果の適用
    result = rotation_effect.apply_rotation(img, concatenated_img, rotation_type)
    
    return result


# メイン処理
if __name__ == "__main__":
    # テスト用のサンプルコード
    result_image = create_rotation_effect("test/album_test.jpg", RotationAxis.SPIN)
    print("回転効果が適用されました")