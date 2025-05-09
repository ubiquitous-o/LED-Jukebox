import os
import numpy as np
from PIL import Image
import time
import ctypes
from OpenGL.GL import *
from OpenGL.GLUT import *

def check_gl_error(operation_name=""):
    """OpenGLのエラーをチェックし、あれば例外を発生させる"""
    err = glGetError()
    if err != GL_NO_ERROR:
        error_str = gluErrorString(err) if 'gluErrorString' in globals() else f"OpenGL Error Code: {err}"
        print(f"OpenGL error after {operation_name}: {error_str}")
        # raise RuntimeError(f"OpenGL error after {operation_name}: {error_str}") # デバッグ中はprintに留めることも
    return err == GL_NO_ERROR


class HeadlessCubeRenderer:
    """FreeGLUTとFBOを使用してオフスクリーンで3Dキューブをレンダリングするクラス"""

    def __init__(self, width=64, height=64):
        """初期化"""
        self.width = width
        self.height = height
        self.glut_window_id = None
        self.fbo = None
        self.fbo_texture = None
        self.texture_id = None
        self.program = None
        self.vao = None
        self.vertex_buffer = None
        self.texture_coords_buffer = None
        self.element_buffer = None
        self.cleaned_up = False # クリーンアップフラグ

        self._init_glut_and_gl_context()
        check_gl_error("GLUT Init")
        self._init_shaders()
        check_gl_error("Shader Init")
        self._init_buffers()
        check_gl_error("Buffer Init")
        self._init_fbo()
        check_gl_error("FBO Init")

    def _init_glut_and_gl_context(self):
        """GLUTの初期化とOpenGLコンテキストの作成"""
        print("Initializing GLUT for offscreen rendering...")
        argv = sys.argv if hasattr(sys, 'argv') and sys.argv else [""]
        glutInit(argv)
        glutInitDisplayMode(GLUT_RGBA | GLUT_DOUBLE | GLUT_DEPTH)
        glutInitWindowSize(self.width, self.height)
        self.glut_window_id = glutCreateWindow("Offscreen Cube Renderer")
        print(f"GLUT window created (ID: {self.glut_window_id}). OpenGL context should be active.")
        
        glViewport(0, 0, self.width, self.height)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glClearColor(0.1, 0.1, 0.1, 1.0) # 背景色を少し明るくして、黒との区別をしやすくする
        glDisable(GL_CULL_FACE) # 明示的にカリングを無効化
        check_gl_error("GL Context Setup")


    def _init_fbo(self):
        """フレームバッファオブジェクト(FBO)の初期化"""
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        check_gl_error("FBO Gen/Bind")

        self.fbo_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.fbo_texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.width, self.height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.fbo_texture, 0)
        check_gl_error("FBO Texture Attachment")

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print("Framebuffer is not complete!") # エラーメッセージを強化
            status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
            if status == GL_FRAMEBUFFER_UNDEFINED: print("GL_FRAMEBUFFER_UNDEFINED")
            elif status == GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT: print("GL_FRAMEBUFFER_INCOMPLETE_ATTACHMENT")
            elif status == GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT: print("GL_FRAMEBUFFER_INCOMPLETE_MISSING_ATTACHMENT")
            elif status == GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER: print("GL_FRAMEBUFFER_INCOMPLETE_DRAW_BUFFER")
            elif status == GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER: print("GL_FRAMEBUFFER_INCOMPLETE_READ_BUFFER")
            elif status == GL_FRAMEBUFFER_UNSUPPORTED: print("GL_FRAMEBUFFER_UNSUPPORTED")
            elif status == GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE: print("GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE")
            elif status == GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS: print("GL_FRAMEBUFFER_INCOMPLETE_LAYER_TARGETS")
            raise RuntimeError("Framebuffer is not complete!")

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        print("FBO initialized successfully.")
        check_gl_error("FBO Init End")

    def _init_shaders(self):
        """シェーダーの初期化 (#version 330 core スタイル)"""
        vertex_shader_src = """
        #version 330 core
        layout (location = 0) in vec3 position;
        layout (location = 1) in vec2 texCoord; // テクスチャ座標を受け取る

        uniform mat4 model;
        uniform mat4 view;
        uniform mat4 projection;

        out vec2 v_texCoord; // テクスチャ座標をフラグメントシェーダーに渡す

        void main() {
            gl_Position = projection * view * model * vec4(position, 1.0);
            v_texCoord = texCoord; // テクスチャ座標を渡す
        }
        """

        # --- デバッグ用: 常に赤色を出力するフラグメントシェーダー ---
        # fragment_shader_src_debug = """
        # #version 330 core
        # out vec4 FragColor;
        # void main() {
        #     FragColor = vec4(1.0, 0.0, 0.0, 1.0); // 赤色
        # }
        # """
        # --- 元のフラグメントシェーダー ---
        fragment_shader_src_original = """
        #version 330 core
        in vec2 v_texCoord; // 頂点シェーダーからテクスチャ座標を受け取る
        out vec4 FragColor;
        uniform sampler2D u_texture; // テクスチャサンプラー
        void main() {
            FragColor = texture(u_texture, v_texCoord); // テクスチャから色を取得
        }
        """
        # 元のシェーダーを使用
        self.program = self._compile_and_link_program(vertex_shader_src, fragment_shader_src_original)

        glUseProgram(self.program)
        print("Shaders initialized and program linked (with texturing).") # メッセージ変更
        check_gl_error("Shader Program Use")

    def _compile_and_link_program(self, vertex_source, fragment_source):
        # ...existing code...
        def compile_shader(source, shader_type):
            shader = glCreateShader(shader_type)
            glShaderSource(shader, source)
            glCompileShader(shader)
            if not glGetShaderiv(shader, GL_COMPILE_STATUS):
                log = glGetShaderInfoLog(shader).decode()
                glDeleteShader(shader)
                raise RuntimeError(f"Shader compilation error ({'vertex' if shader_type == GL_VERTEX_SHADER else 'fragment'}): {log}")
            return shader

        vertex_shader = compile_shader(vertex_source, GL_VERTEX_SHADER)
        fragment_shader = compile_shader(fragment_source, GL_FRAGMENT_SHADER)

        program = glCreateProgram()
        glAttachShader(program, vertex_shader)
        glAttachShader(program, fragment_shader)
        glLinkProgram(program)

        if not glGetProgramiv(program, GL_LINK_STATUS):
            log = glGetProgramInfoLog(program).decode()
            glDeleteProgram(program)
            glDeleteShader(vertex_shader)
            glDeleteShader(fragment_shader)
            raise RuntimeError(f"Shader program linking error: {log}")

        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        return program

    def _init_buffers(self):
        # ...existing code...
        vertices = np.array([
            # 前面
            -0.5, -0.5,  0.5,  0.5, -0.5,  0.5,   0.5,  0.5,  0.5,  -0.5,  0.5,  0.5,
            # 背面
            -0.5, -0.5, -0.5,  0.5, -0.5, -0.5,   0.5,  0.5, -0.5,  -0.5,  0.5, -0.5,
            # 上面
            -0.5,  0.5,  0.5,  0.5,  0.5,  0.5,   0.5,  0.5, -0.5,  -0.5,  0.5, -0.5,
            # 下面
            -0.5, -0.5,  0.5,  0.5, -0.5,  0.5,   0.5, -0.5, -0.5,  -0.5, -0.5, -0.5,
            # 右面
             0.5, -0.5,  0.5,  0.5, -0.5, -0.5,   0.5,  0.5, -0.5,   0.5,  0.5,  0.5,
            # 左面
            -0.5, -0.5,  0.5, -0.5, -0.5, -0.5,  -0.5,  0.5, -0.5,  -0.5,  0.5,  0.5,
        ], dtype=np.float32)

        tex_coords = np.array([
            0.0, 1.0,  1.0, 1.0,  1.0, 0.0,  0.0, 0.0,
            1.0, 1.0,  0.0, 1.0,  0.0, 0.0,  1.0, 0.0,
            0.0, 1.0,  1.0, 1.0,  1.0, 0.0,  0.0, 0.0,
            0.0, 0.0,  1.0, 0.0,  1.0, 1.0,  0.0, 1.0,
            0.0, 1.0,  1.0, 1.0,  1.0, 0.0,  0.0, 0.0,
            1.0, 1.0,  0.0, 1.0,  0.0, 0.0,  1.0, 0.0,
        ], dtype=np.float32)

        indices = np.array([
             0,  1,  2,   2,  3,  0,  # 前面
             4,  5,  6,   6,  7,  4,  # 背面
             8,  9, 10,  10, 11,  8,  # 上面
            12, 13, 14,  14, 15, 12,  # 下面
            16, 17, 18,  18, 19, 16,  # 右面
            20, 21, 22,  22, 23, 20,  # 左面
        ], dtype=np.uint16)

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)
        check_gl_error("VAO Gen/Bind")

        self.vertex_buffer = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        check_gl_error("Vertex Buffer")

        self.texture_coords_buffer = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.texture_coords_buffer)
        glBufferData(GL_ARRAY_BUFFER, tex_coords.nbytes, tex_coords, GL_STATIC_DRAW)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(1) # テクスチャを使わないシェーダーでも、属性は有効にしておく（無害）
        check_gl_error("Texture Coords Buffer")


        self.element_buffer = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.element_buffer)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        check_gl_error("Element Buffer")

        glBindVertexArray(0)

        self.texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        # ダミーテクスチャデータ（1x1ピクセルの白）を設定しておく
        dummy_pixel = np.array([255, 255, 255], dtype=np.uint8)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 1, 1, 0, GL_RGB, GL_UNSIGNED_BYTE, dummy_pixel)
        glBindTexture(GL_TEXTURE_2D, 0)
        print("Buffers (VBO, EBO, VAO) initialized.")
        check_gl_error("Buffer Init End")

    def set_texture(self, image: Image.Image):
        # ...existing code...
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        img_data = image.tobytes()

        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.width, image.height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
        glBindTexture(GL_TEXTURE_2D, 0)
        print(f"Texture set from image (size: {image.size})")
        check_gl_error(f"Set Texture {image.size}")

    def render(self, rotation_x, rotation_y, rotation_z):
        """キューブをFBOにレンダリングする"""
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.width, self.height)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        check_gl_error("Render Start / Clear")

        glUseProgram(self.program)

        model = self._get_rotation_matrix(rotation_x, rotation_y, rotation_z)
        view = self._get_view_matrix(0, 0, 2.5)
        projection = self._get_projection_matrix(45.0, self.width / self.height, 0.1, 100.0)

        glUniformMatrix4fv(glGetUniformLocation(self.program, "model"), 1, GL_FALSE, model.T)
        glUniformMatrix4fv(glGetUniformLocation(self.program, "view"), 1, GL_FALSE, view.T)
        glUniformMatrix4fv(glGetUniformLocation(self.program, "projection"), 1, GL_FALSE, projection.T)
        check_gl_error("Uniform Matrices")

        # --- テクスチャ関連を有効にする ---
        glActiveTexture(GL_TEXTURE0) # テクスチャユニット0を有効化
        glBindTexture(GL_TEXTURE_2D, self.texture_id) # 作成したテクスチャをバインド
        glUniform1i(glGetUniformLocation(self.program, "u_texture"), 0) # シェーダーのu_textureサンプラーにテクスチャユニット0を割り当て
        check_gl_error("Uniform Texture")
        # --- ここまで ---

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, 36, GL_UNSIGNED_SHORT, None)
        check_gl_error("Draw Elements")
        glBindVertexArray(0)

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        check_gl_error("Render End")


    def _get_rotation_matrix(self, angle_x, angle_y, angle_z):
        # ...existing code...
        rad_x = np.radians(angle_x)
        cos_x, sin_x = np.cos(rad_x), np.sin(rad_x)
        rot_x = np.array([[1, 0, 0, 0], [0, cos_x, -sin_x, 0], [0, sin_x, cos_x, 0], [0, 0, 0, 1]], dtype=np.float32)
        rad_y = np.radians(angle_y)
        cos_y, sin_y = np.cos(rad_y), np.sin(rad_y)
        rot_y = np.array([[cos_y, 0, sin_y, 0], [0, 1, 0, 0], [-sin_y, 0, cos_y, 0], [0, 0, 0, 1]], dtype=np.float32)
        rad_z = np.radians(angle_z)
        cos_z, sin_z = np.cos(rad_z), np.sin(rad_z)
        rot_z = np.array([[cos_z, -sin_z, 0, 0], [sin_z, cos_z, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32)
        
        return rot_z @ rot_y @ rot_x

    def _get_view_matrix(self, eye_x, eye_y, eye_z, center_x=0, center_y=0, center_z=0, up_x=0, up_y=1, up_z=0):
        # ...existing code...
        eye = np.array([eye_x, eye_y, eye_z])
        center = np.array([center_x, center_y, center_z])
        up = np.array([up_x, up_y, up_z])

        f = center - eye
        f_norm = f / np.linalg.norm(f)
        
        s = np.cross(f_norm, up)
        s_norm = s / np.linalg.norm(s)
        
        u = np.cross(s_norm, f_norm)

        # OpenGLのLookAt行列の標準的な形式に合わせる
        # t = -eye
        # M_view = [ s_norm[0]  s_norm[1]  s_norm[2]  dot(s_norm, t) ]
        #          [ u[0]       u[1]       u[2]       dot(u, t)      ]
        #          [-f_norm[0] -f_norm[1] -f_norm[2]  dot(-f_norm, t)]
        #          [ 0          0          0          1              ]
        # PyOpenGLの glTranslate, glRotate のような固定機能パイプラインの行列とは異なる
        # GLMのlookAtに近い形
        
        view_matrix = np.identity(4, dtype=np.float32)
        view_matrix[0,0:3] = s_norm
        view_matrix[1,0:3] = u
        view_matrix[2,0:3] = -f_norm # カメラは-Z方向を向く

        view_matrix[0,3] = -np.dot(s_norm, eye)
        view_matrix[1,3] = -np.dot(u, eye)
        view_matrix[2,3] =  np.dot(f_norm, eye) # -np.dot(-f_norm, eye) と同じ

        return view_matrix # numpyの配列は行優先なので、転置は不要 (シェーダー側で列としてアクセス)
                           # ただし、glUniformMatrix4fv の transpose 引数が GL_FALSE の場合、
                           # シェーダー側では列優先として扱われるため、このままで良い。
                           # もしシェーダー側で行列を M * v のように使うなら、転置が必要になる場合がある。
                           # 一般的には、OpenGLの行列は列優先。

    def _get_projection_matrix(self, fov_y_degrees, aspect_ratio, near_plane, far_plane):
        # ...existing code...
        fov_y_rad = np.radians(fov_y_degrees)
        f = 1.0 / np.tan(fov_y_rad / 2.0)
        # OpenGLの標準的な射影行列
        projection_matrix = np.zeros((4,4), dtype=np.float32)
        projection_matrix[0,0] = f / aspect_ratio
        projection_matrix[1,1] = f
        projection_matrix[2,2] = (far_plane + near_plane) / (near_plane - far_plane)
        projection_matrix[2,3] = (2 * far_plane * near_plane) / (near_plane - far_plane)
        projection_matrix[3,2] = -1.0
        return projection_matrix


    def get_image(self) -> Image.Image:
        # ...existing code...
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glReadBuffer(GL_COLOR_ATTACHMENT0)
        pixels = glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE)
        check_gl_error("Read Pixels")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        image = Image.frombytes("RGB", (self.width, self.height), pixels)
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
        return image

    def cleanup(self):
        if self.cleaned_up:
            print("HeadlessCubeRenderer already cleaned up.")
            return
        print("Cleaning up HeadlessCubeRenderer resources...")
        # ... (既存の解放処理) ...
        if self.fbo: glDeleteFramebuffers(1, [self.fbo]); self.fbo = None
        if self.fbo_texture: glDeleteTextures(1, [self.fbo_texture]); self.fbo_texture = None
        if self.texture_id: glDeleteTextures(1, [self.texture_id]); self.texture_id = None
        if self.program: glDeleteProgram(self.program); self.program = None
        if self.vao: glDeleteVertexArrays(1, [self.vao]); self.vao = None
        if self.vertex_buffer: glDeleteBuffers(1, [self.vertex_buffer]); self.vertex_buffer = None
        if self.texture_coords_buffer: glDeleteBuffers(1, [self.texture_coords_buffer]); self.texture_coords_buffer = None
        if self.element_buffer: glDeleteBuffers(1, [self.element_buffer]); self.element_buffer = None

        if self.glut_window_id:
            try:
                current_window = glutGetWindow()
                if current_window != 0 and current_window != self.glut_window_id: # 0はウィンドウがない状態
                    # 他のウィンドウがアクティブな場合、エラーになることがあるので注意
                    # glutSetWindow(self.glut_window_id) # これがエラーの原因になることも
                    pass
                if glutGetWindow() == self.glut_window_id : # 念のため現在のウィンドウIDを確認
                     glutDestroyWindow(self.glut_window_id)
                     print(f"GLUT window {self.glut_window_id} destroyed.")
                elif current_window == 0 and self.glut_window_id : # ウィンドウコンテキストがないがIDは保持している場合
                    # このケースでは安全に破棄できないかもしれない
                    print(f"GLUT window {self.glut_window_id} might not be destroyable without active context.")
                    pass


            except Exception as e:
                print(f"Error destroying GLUT window: {e}")
            self.glut_window_id = None
        
        print("HeadlessCubeRenderer cleanup finished.")
        self.cleaned_up = True

    # __del__ は、リソース解放のタイミングが保証されないため、明示的な cleanup 呼び出しを推奨
    # def __del__(self):
    #     self.cleanup()