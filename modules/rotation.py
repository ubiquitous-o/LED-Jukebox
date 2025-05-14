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
        self.max_angle = 0
    
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
        self.max_angle = max_angle
        angle = 0
        # ダブルバッファリング用のキャンバスを作成
        double_buffer = self.matrix.CreateFrameCanvas()

        img_0 = concat_img.crop((0, 0, img.width, img.height)) # top panel
        img_1 = concat_img.crop((img.width, 0, img.width*2, img.height)) #side panel
        img_2 = concat_img.crop((img.width*2, 0, img.width*3, img.height)) #side panel
        img_3 = concat_img.crop((img.width*3, 0, img.width*4, img.height)) #side panel
        img_4 = concat_img.crop((img.width*4, 0, img.width*5, img.height)) #side panel
        img_5 = concat_img.crop((img.width*5, 0, img.width*6, img.height)) #bottom panel (not shown)
        imgs = [img_0, img_1, img_2, img_3, img_4, img_5]

        # 回転処理
        while not self.led_matrix.stop_display and angle <= max_angle:
            # キャンバスをクリア
            double_buffer.Clear()
            
            # 現在の角度と次の角度での画像を生成
            current_img = self._rotate_cube(imgs, angle, rotation_axis)
            next_img = self._rotate_cube(imgs, angle + 1, rotation_axis)
            
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

    def _create_scroll_img(self, source, target, offset, axis, invert_scroll=False, flip=False, direction_swap=False):
        if axis == RotationAxis.X_INC or axis == RotationAxis.X_DEC:

            if flip:
                source = source.transpose(Image.FLIP_TOP_BOTTOM)
                source = source.transpose(Image.FLIP_LEFT_RIGHT)
 
            if invert_scroll:
                cropped_img = source.crop((0, source.height-offset, source.width, source.height))
                offsseted_img = target.crop((0, 0, target.width, target.height-offset))
                result_scroll_img = Image.new('RGB', (target.width, target.height))
                result_scroll_img.paste(cropped_img, (0, 0))
                result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
 
            else:
                cropped_img = target.crop((0, offset, source.width, source.height))
                offsseted_img = source.crop((0, 0, target.width, offset))
                result_scroll_img = Image.new('RGB', (target.width, target.height))
                result_scroll_img.paste(cropped_img, (0, 0))
                result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
            return result_scroll_img

        elif axis == RotationAxis.Y_INC or axis == RotationAxis.Y_DEC:
            if invert_scroll:
                cropped_img = target.crop((offset, 0, source.width, source.height))
                offsseted_img = source.crop((0, 0, offset, target.height))
                result_scroll_img = Image.new('RGB', (target.width, target.height))
                result_scroll_img.paste(cropped_img, (0, 0))
                result_scroll_img.paste(offsseted_img, (cropped_img.width, 0))
            else:
                cropped_img = source.crop((source.width - offset, 0, source.width, source.height))
                offsseted_img = target.crop((0, 0, target.width - offset, target.height))
                result_scroll_img = Image.new('RGB', (target.width, target.height))
                result_scroll_img.paste(cropped_img, (0, 0))
                result_scroll_img.paste(offsseted_img, (cropped_img.width, 0))
            return result_scroll_img
        
        elif axis == RotationAxis.Z_INC:
            # horizontal scroll
            if direction_swap:
                if invert_scroll:
                    source = source.rotate(90, resample=Image.BICUBIC)
                    cropped_img = target.crop((offset, 0, target.width, target.height))
                    offsseted_img = source.crop((0, 0, offset, target.height))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (cropped_img.width, 0))
                else:
                    source = source.rotate(90, resample=Image.BICUBIC)
                    cropped_img = source.crop((target.width - offset, 0, source.width, source.height))
                    offsseted_img = target.crop((0, 0, target.width - offset, target.height))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
            # vertical scroll
            else:
                if invert_scroll:
                    source = source.rotate(90, resample=Image.BICUBIC)
                    cropped_img = source.crop((0, target.height-offset, source.width, source.height))
                    offsseted_img = target.crop((0, 0, target.width, target.height-offset))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
                else:
                    source = source.rotate(-90, resample=Image.BICUBIC)
                    cropped_img = target.crop((0, offset, source.width, source.height))
                    offsseted_img = source.crop((0, 0, target.height, offset))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
            return result_scroll_img

        elif axis == RotationAxis.Z_DEC:
            # horizontal scroll
            if direction_swap:
                if invert_scroll:
                    source = source.rotate(90, resample=Image.BICUBIC)
                    cropped_img = target.crop((offset, 0, target.width, target.height))
                    offsseted_img = source.crop((0, 0, offset, target.height))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (cropped_img.width, 0))
                else:
                    source = source.rotate(-90, resample=Image.BICUBIC)
                    cropped_img = source.crop((source.width - offset, 0, source.width, source.height))
                    offsseted_img = target.crop((0, 0, target.width - offset, target.height))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (cropped_img.width, 0))
            # vertical scroll
            else:
                if invert_scroll:
                    source = source.rotate(-90, resample=Image.BICUBIC)
                    cropped_img = source.crop((0, target.height-offset, source.width, source.height))
                    offsseted_img = target.crop((0, 0, target.width, target.height-offset))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
                else:
                    source = source.rotate(-90, resample=Image.BICUBIC)
                    cropped_img = target.crop((0, offset, source.width, source.height))
                    offsseted_img = source.crop((0, 0, target.height, offset))
                    result_scroll_img = Image.new('RGB', (target.width, target.height))
                    result_scroll_img.paste(cropped_img, (0, 0))
                    result_scroll_img.paste(offsseted_img, (0, cropped_img.height))
            return result_scroll_img
        else:
            print(f"サポートされていない回転軸: {axis}")

    def _rotate_cube(self, imgs, angle, rotation_axis):
        """指定された軸に沿って画像を回転させる"""
        image = imgs[0]
        final_render = Image.new('RGB', (image.width * 6, image.height))
        offset = int((angle / self.max_angle) * image.height)
        
        if rotation_axis == RotationAxis.X_INC:
            # scroll: 5 -> 4 -> 0 -> 2
            # rotate: 1, 3
            new_0_img = self._create_scroll_img(imgs[4], imgs[0], offset, rotation_axis, invert_scroll=False)
            new_2_img = self._create_scroll_img(imgs[0], imgs[2], offset, rotation_axis, invert_scroll=True, flip=True)
            new_4_img = self._create_scroll_img(imgs[5], imgs[4], offset, rotation_axis, invert_scroll=False)
            new_5_img = self._create_scroll_img(imgs[2], imgs[5], offset, rotation_axis, invert_scroll=True)
            
            new_1_img = imgs[1].rotate(-angle, resample=Image.BICUBIC)
            new_3_img = imgs[3].rotate(angle, resample=Image.BICUBIC)

            final_render.paste(new_0_img, (0, 0))
            final_render.paste(new_1_img, (image.width, 0))
            final_render.paste(new_2_img, (image.width*2, 0))
            final_render.paste(new_3_img, (image.width*3, 0))
            final_render.paste(new_4_img, (image.width*4, 0))
            final_render.paste(new_5_img, (image.width*5, 0))

            return final_render
        
        elif rotation_axis == RotationAxis.X_DEC:
            # scroll: 2 -> 0 -> 4 -> 5
            # rotate: 1, 3
            new_0_img = self._create_scroll_img(imgs[2], imgs[0], offset, rotation_axis, invert_scroll=True, flip=True)
            new_2_img = self._create_scroll_img(imgs[5], imgs[2], offset, rotation_axis, invert_scroll=False)
            new_4_img = self._create_scroll_img(imgs[0], imgs[4], offset, rotation_axis, invert_scroll=True)
            new_5_img = self._create_scroll_img(imgs[4], imgs[5], offset, rotation_axis, invert_scroll=False)
            
            new_1_img = imgs[1].rotate(angle, resample=Image.BICUBIC)
            new_3_img = imgs[3].rotate(-angle, resample=Image.BICUBIC)

            final_render.paste(new_0_img, (0, 0))
            final_render.paste(new_1_img, (image.width, 0))
            final_render.paste(new_2_img, (image.width*2, 0))
            final_render.paste(new_3_img, (image.width*3, 0))
            final_render.paste(new_4_img, (image.width*4, 0))
            final_render.paste(new_5_img, (image.width*5, 0))

            return final_render

        elif rotation_axis == RotationAxis.Y_INC:
            # scroll: 1 -> 2 -> 3 -> 4
            # rotate: 0, 5
            new_1_img = self._create_scroll_img(imgs[4], imgs[1], offset, rotation_axis, invert_scroll=True)
            new_2_img = self._create_scroll_img(imgs[1], imgs[2], offset, rotation_axis, invert_scroll=True)
            new_3_img = self._create_scroll_img(imgs[2], imgs[3], offset, rotation_axis, invert_scroll=True)
            new_4_img = self._create_scroll_img(imgs[3], imgs[4], offset, rotation_axis, invert_scroll=True)
            
            new_0_img = imgs[0].rotate(-angle, resample=Image.BICUBIC)
            new_5_img = imgs[5].rotate(angle, resample=Image.BICUBIC)

            final_render.paste(new_0_img, (0, 0))
            final_render.paste(new_1_img, (image.width, 0))
            final_render.paste(new_2_img, (image.width*2, 0))
            final_render.paste(new_3_img, (image.width*3, 0))
            final_render.paste(new_4_img, (image.width*4, 0))
            final_render.paste(new_5_img, (image.width*5, 0))

            return final_render
        elif rotation_axis == RotationAxis.Y_DEC:
            # scroll: 4 -> 3 -> 2 -> 1
            # rotate: 0, 5
            new_1_img = self._create_scroll_img(imgs[2], imgs[1], offset, rotation_axis, invert_scroll=False)
            new_2_img = self._create_scroll_img(imgs[1], imgs[2], offset, rotation_axis, invert_scroll=False)
            new_3_img = self._create_scroll_img(imgs[2], imgs[3], offset, rotation_axis, invert_scroll=False)
            new_4_img = self._create_scroll_img(imgs[3], imgs[4], offset, rotation_axis, invert_scroll=False)
            
            new_0_img = imgs[0].rotate(angle, resample=Image.BICUBIC)
            new_5_img = imgs[5].rotate(-angle, resample=Image.BICUBIC)
            
            final_render.paste(new_0_img, (0, 0))
            final_render.paste(new_1_img, (image.width, 0))
            final_render.paste(new_2_img, (image.width*2, 0))
            final_render.paste(new_3_img, (image.width*3, 0))
            final_render.paste(new_4_img, (image.width*4, 0))
            final_render.paste(new_5_img, (image.width*5, 0))
            return final_render

        elif rotation_axis == RotationAxis.Z_INC:
            # scroll: 5 -> 1 -> 0 -> 3
            # rotate: 2, 4
            new_0_img = self._create_scroll_img(imgs[1], imgs[0], offset, rotation_axis, invert_scroll=True, direction_swap=True)
            new_1_img = self._create_scroll_img(imgs[5], imgs[1], offset, rotation_axis, invert_scroll=False)
            new_3_img = self._create_scroll_img(imgs[0], imgs[3], offset, rotation_axis, invert_scroll=True)
            new_5_img = self._create_scroll_img(imgs[3], imgs[5], offset, rotation_axis, invert_scroll=False, direction_swap=True)
            
            new_2_img = imgs[2].rotate(-angle, resample=Image.BICUBIC)
            new_4_img = imgs[4].rotate(angle, resample=Image.BICUBIC)

            final_render.paste(new_0_img, (0, 0))
            final_render.paste(new_1_img, (image.width, 0))
            final_render.paste(new_2_img, (image.width*2, 0))
            final_render.paste(new_3_img, (image.width*3, 0))
            final_render.paste(new_4_img, (image.width*4, 0))
            final_render.paste(new_5_img, (image.width*5, 0))

            return final_render
        
        elif rotation_axis == RotationAxis.Z_DEC:
            # scroll: 3 -> 0 -> 1 -> 5
            # rotate: 2, 4
            new_0_img = self._create_scroll_img(imgs[3], imgs[0], offset, rotation_axis, invert_scroll=False, direction_swap=True)
            new_1_img = self._create_scroll_img(imgs[0], imgs[1], offset, rotation_axis, invert_scroll=True)
            new_3_img = self._create_scroll_img(imgs[5], imgs[3], offset, rotation_axis, invert_scroll=False)
            new_5_img = self._create_scroll_img(imgs[1], imgs[5], offset, rotation_axis, invert_scroll=True, direction_swap=True)
            
            new_2_img = imgs[2].rotate(angle, resample=Image.BICUBIC)
            new_4_img = imgs[4].rotate(-angle, resample=Image.BICUBIC)

            final_render.paste(new_0_img, (0, 0))
            final_render.paste(new_1_img, (image.width, 0))
            final_render.paste(new_2_img, (image.width*2, 0))
            final_render.paste(new_3_img, (image.width*3, 0))
            final_render.paste(new_4_img, (image.width*4, 0))
            final_render.paste(new_5_img, (image.width*5, 0))

            return final_render
            
        else:
            print(f"サポートされていない回転軸: {rotation_axis}")
            return Image.new('RGB', (image.width * 5, image.height), color=(0, 0, 0))