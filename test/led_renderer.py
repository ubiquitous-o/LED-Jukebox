import os
import numpy as np
from PIL import Image
import time
import ctypes
from OpenGL.GL import *
from OpenGL.GLUT import *
import sys

def check_gl_error(operation_name=""):
    """OpenGLのエラーをチェックし、あれば例外を発生させる"""
    err = glGetError()
    if (err != GL_NO_ERROR):
        error_str = gluErrorString(err) if 'gluErrorString' in globals() else f"OpenGL Error Code: {err}"
        print(f"OpenGL error after {operation_name}: {error_str}")
        # raise RuntimeError(f"OpenGL error after {operation_name}: {error_str}") # デバッグ中はprintに留めることも
    return err == GL_NO_ERROR


class HeadlessCubeRenderer:
    """FreeGLUTとFBOを使用してオフスクリーンで3Dキューブをレンダリングするクラス (キューブマップ使用)"""

    FACE_FRONT = 0  # +Z
    FACE_BACK = 1   # -Z
    FACE_LEFT = 2   # -X
    FACE_RIGHT = 3  # +X
    FACE_TOP = 4    # +Y
    FACE_BOTTOM = 5 # -Y

    ROTATION_AXIS_NONE = -1 # 回転なし
    ROTATION_AXIS_X = 0     # X軸周りのテクスチャ回転 (Vスクロール + L/R面内回転)
    ROTATION_AXIS_Y = 1     # Y軸周りのテクスチャ回転 (Uスクロール + T/B面内回転)
    ROTATION_AXIS_Z = 2     # Z軸周りのテクスチャ回転 (特定面スクロール + F/B面内回転)

    # OpenGLのキューブマップターゲット順序に対応
    CUBEMAP_TARGETS = [
        GL_TEXTURE_CUBE_MAP_POSITIVE_X, # Right
        GL_TEXTURE_CUBE_MAP_NEGATIVE_X, # Left
        GL_TEXTURE_CUBE_MAP_POSITIVE_Y, # Top
        GL_TEXTURE_CUBE_MAP_NEGATIVE_Y, # Bottom
        GL_TEXTURE_CUBE_MAP_POSITIVE_Z, # Front
        GL_TEXTURE_CUBE_MAP_NEGATIVE_Z  # Back
    ]
    def __init__(self, width=64, height=64, face_order_ids_for_stitch=None):
        """初期化"""
        self.width = width
        self.height = height
        self.glut_window_id = None
        self.fbo = None
        self.fbo_texture = None
        self.panorama_texture_id = None # cubemap_texture_id から変更
        self.program = None
        self.vao = None
        self.vertex_buffer = None
        self.element_buffer = None
        self.cleaned_up = False

        if face_order_ids_for_stitch is None:
            # 展開図の順序: TOP, FRONT, RIGHT, BACK, LEFT, BOTTOM
            self.face_order_ids_for_stitch = [
                self.FACE_TOP, self.FACE_FRONT, self.FACE_RIGHT,
                self.FACE_BACK, self.FACE_LEFT, self.FACE_BOTTOM
            ]
        else:
            self.face_order_ids_for_stitch = face_order_ids_for_stitch


        self._init_glut_and_gl_context()
        check_gl_error("GLUT Init")
        self._init_shaders() # シェーダー内容が変更されます
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
        
        glEnable(GL_CULL_FACE)
        glCullFace(GL_BACK)
        glFrontFace(GL_CCW)
        
        glClearColor(0.1, 0.1, 0.1, 1.0) 
        check_gl_error("GL Context Setup")

    def _init_shaders(self):
        """シェーダーの初期化 (単一2Dテクスチャ用)"""
        vertex_shader_src = """
        #version 330 core
        layout (location = 0) in vec3 a_position;
        layout (location = 1) in vec2 a_texCoord; // UV座標を受け取る

        uniform mat4 model;
        uniform mat4 view;
        uniform mat4 projection;

        out vec2 v_texCoord_fs; // フラグメントシェーダーに渡すUV座標

        void main() {
            gl_Position = projection * view * model * vec4(a_position, 1.0);
            v_texCoord_fs = a_texCoord; // UV座標をそのまま渡す
        }
        """
        fragment_shader_src = """
        #version 330 core
        in vec2 v_texCoord_fs;
        out vec4 FragColor;

        uniform sampler2D u_panoramaTexture;
        uniform mat3 u_textureTransform; // 面内回転用
        uniform vec2 u_scrollOffsetVec;    // x: Uスクロール(Y軸回転), y: Vスクロール(X軸回転)
        uniform int u_currentRenderingFaceID; // Pythonの HeadlessCubeRenderer.FACE_*
        uniform int u_rotationAxis;           // Pythonの HeadlessCubeRenderer.ROTATION_AXIS_*
        uniform bool u_invertVForLed;      // V方向のLEDスクロール表示を反転するか (追加)

        // Python側の FACE_* 定義と一致させる (これらは論理面のID)
        const int LOGICAL_FACE_FRONT = 0;
        const int LOGICAL_FACE_BACK = 1;
        const int LOGICAL_FACE_LEFT = 2;
        const int LOGICAL_FACE_RIGHT = 3;
        const int LOGICAL_FACE_TOP = 4;
        const int LOGICAL_FACE_BOTTOM = 5;

        // Python側の ROTATION_AXIS_* 定義と一致させる
        const int AXIS_NONE = -1;
        const int AXIS_X = 0;
        const int AXIS_Y = 1;
        const int AXIS_Z = 2;

        // アトラスの物理スロット番号 (test_renderer.py のアトラス作成順序に基づく)
        const int ATLAS_SLOT_TOP = 0;
        const int ATLAS_SLOT_FRONT = 1;
        const int ATLAS_SLOT_RIGHT = 2;
        const int ATLAS_SLOT_BACK = 3;
        const int ATLAS_SLOT_LEFT = 4;
        const int ATLAS_SLOT_BOTTOM = 5;

        const float ATLAS_COLS = 6.0;
        const float ATLAS_ROWS = 1.0;

        void main() {
            vec2 base_uv = v_texCoord_fs;
            // 面内回転は最初に行う (u_textureTransform はPython側で軸と面に応じて設定される)
            vec2 uv_after_local_rotation = (u_textureTransform * vec3(base_uv, 1.0)).xy;
            
            vec2 final_atlas_uv;
            vec2 uv_scale_per_slot = vec2(1.0 / ATLAS_COLS, 1.0 / ATLAS_ROWS);
            float atlas_slot_for_current_face; // 基本となるアトラススロット

            // 現在レンダリング中の論理面IDに基づいて、デフォルトのアトラススロットを決定
            if (u_currentRenderingFaceID == LOGICAL_FACE_TOP) atlas_slot_for_current_face = float(ATLAS_SLOT_TOP);
            else if (u_currentRenderingFaceID == LOGICAL_FACE_FRONT) atlas_slot_for_current_face = float(ATLAS_SLOT_FRONT);
            else if (u_currentRenderingFaceID == LOGICAL_FACE_RIGHT) atlas_slot_for_current_face = float(ATLAS_SLOT_RIGHT);
            else if (u_currentRenderingFaceID == LOGICAL_FACE_BACK) atlas_slot_for_current_face = float(ATLAS_SLOT_BACK);
            else if (u_currentRenderingFaceID == LOGICAL_FACE_LEFT) atlas_slot_for_current_face = float(ATLAS_SLOT_LEFT);
            else if (u_currentRenderingFaceID == LOGICAL_FACE_BOTTOM) atlas_slot_for_current_face = float(ATLAS_SLOT_BOTTOM);
            else atlas_slot_for_current_face = float(ATLAS_SLOT_FRONT); // Fallback

            vec2 default_slot_offset = vec2(atlas_slot_for_current_face / ATLAS_COLS, 0.0);

            if (u_rotationAxis == AXIS_Y) { // Y軸回転 (Uスクロール - 面またぎ)
                if (u_currentRenderingFaceID == LOGICAL_FACE_FRONT ||
                    u_currentRenderingFaceID == LOGICAL_FACE_RIGHT ||
                    u_currentRenderingFaceID == LOGICAL_FACE_BACK ||
                    u_currentRenderingFaceID == LOGICAL_FACE_LEFT) { // Uスクロール対象面

                    float strip_segment_start_offset_u = 0.0; // F,R,B,Lのストリップ上の開始インデックス
                    if(u_currentRenderingFaceID == LOGICAL_FACE_FRONT) strip_segment_start_offset_u = 0.0;
                    else if(u_currentRenderingFaceID == LOGICAL_FACE_RIGHT) strip_segment_start_offset_u = 1.0;
                    else if(u_currentRenderingFaceID == LOGICAL_FACE_BACK) strip_segment_start_offset_u = 2.0;
                    else if(u_currentRenderingFaceID == LOGICAL_FACE_LEFT) strip_segment_start_offset_u = 3.0;

                    // 仮想ストリップ上のU座標 = 面内回転後のU + (現在の面のストリップ開始位置 - 全体スクロール量)
                    float u_coord_on_virtual_strip = uv_after_local_rotation.x + (strip_segment_start_offset_u - u_scrollOffsetVec.x);
                    
                    u_coord_on_virtual_strip = mod(u_coord_on_virtual_strip, 4.0);
                    if (u_coord_on_virtual_strip < 0.0) u_coord_on_virtual_strip += 4.0;

                    float source_logical_face_index_u = floor(u_coord_on_virtual_strip); // どの初期論理面からサンプリングするか (0:F, 1:R, 2:B, 3:L)
                    float u_on_selected_logical_face = fract(u_coord_on_virtual_strip);  // その論理面上のU座標
                    
                    vec2 uv_for_sampling = vec2(u_on_selected_logical_face, uv_after_local_rotation.y); 

                    float atlas_slot_u_scroll; // サンプリング元のアトラススロット
                    if (source_logical_face_index_u == 0.0) atlas_slot_u_scroll = float(ATLAS_SLOT_FRONT);
                    else if (source_logical_face_index_u == 1.0) atlas_slot_u_scroll = float(ATLAS_SLOT_RIGHT);
                    else if (source_logical_face_index_u == 2.0) atlas_slot_u_scroll = float(ATLAS_SLOT_BACK);
                    else atlas_slot_u_scroll = float(ATLAS_SLOT_LEFT);
                    
                    vec2 slot_offset_u_scroll = vec2(atlas_slot_u_scroll / ATLAS_COLS, 0.0);
                    final_atlas_uv = slot_offset_u_scroll + uv_for_sampling * uv_scale_per_slot;
                } else { // TOP, BOTTOM 面 (Uスクロール対象外、面内回転のみ)
                    final_atlas_uv = default_slot_offset + uv_after_local_rotation * uv_scale_per_slot;
                }
            } else if (u_rotationAxis == AXIS_X) { // X軸回転 (Vスクロール - 面またぎ)
                if (u_currentRenderingFaceID == LOGICAL_FACE_FRONT ||
                    u_currentRenderingFaceID == LOGICAL_FACE_TOP ||
                    u_currentRenderingFaceID == LOGICAL_FACE_BACK ||
                    u_currentRenderingFaceID == LOGICAL_FACE_BOTTOM) { // Vスクロール対象面

                    // 新しい仮想ストリップ順: FRONT(0) -> TOP(1) -> BACK(2) -> BOTTOM(3)
                    float strip_segment_start_offset_v = 0.0;
                    if (u_currentRenderingFaceID == LOGICAL_FACE_FRONT) strip_segment_start_offset_v = 0.0;
                    else if (u_currentRenderingFaceID == LOGICAL_FACE_TOP) strip_segment_start_offset_v = 1.0;
                    else if (u_currentRenderingFaceID == LOGICAL_FACE_BACK) strip_segment_start_offset_v = 2.0;
                    else if (u_currentRenderingFaceID == LOGICAL_FACE_BOTTOM) strip_segment_start_offset_v = 3.0;

                    // u_scrollOffsetVec.y はPython側で「LED表示上のスクロール方向」を制御するために設定される。
                    // 負の値: LED表示上「上から下へ」 (テクスチャのサンプリングV座標が減少)
                    // 正の値: LED表示上「下から上へ」 (テクスチャのサンプリングV座標が増加)
                    float v_coord_on_virtual_strip = uv_after_local_rotation.y + strip_segment_start_offset_v + u_scrollOffsetVec.y; // 符号を元に戻しました
                    v_coord_on_virtual_strip = mod(v_coord_on_virtual_strip, 4.0);
                    
                    if (v_coord_on_virtual_strip < 0.0) v_coord_on_virtual_strip += 4.0;

                    float source_logical_face_index_v = floor(v_coord_on_virtual_strip);
                    float u_src_raw = uv_after_local_rotation.x; // X軸回転の場合、U座標は面内回転後のもの
                    float v_src_raw = fract(v_coord_on_virtual_strip); // スクロールと面遷移のみを考慮したV座標

                    // 面接続のためのV方向フリップを決定
                    // X軸回転におけるU方向フリップは、提示された接続ルールでは不要と判断
                    bool conn_v_flip = false;
                    if (u_currentRenderingFaceID == LOGICAL_FACE_FRONT) {
                        if (source_logical_face_index_v == 1.0) { /* T -> F (Fの上端 vs Tの上端) */ conn_v_flip = false; }
                        else if (source_logical_face_index_v == 3.0) { /* Bo -> F (Fの下端 vs Boの上端) */ conn_v_flip = true; }
                    } else if (u_currentRenderingFaceID == LOGICAL_FACE_TOP) {
                        if (source_logical_face_index_v == 0.0) { /* F -> T (Tの上端 vs Fの上端) */ conn_v_flip = false; }
                        else if (source_logical_face_index_v == 2.0) { /* B -> T (Tの下端 vs Bの上端) */ conn_v_flip = true; }
                    } else if (u_currentRenderingFaceID == LOGICAL_FACE_BACK) {
                        if (source_logical_face_index_v == 1.0) { /* T -> B (Bの上端 vs Tの下端) */ conn_v_flip = true; }
                        else if (source_logical_face_index_v == 3.0) { /* Bo -> B (Bの下端 vs Boの下端) */ conn_v_flip = false; }
                    } else if (u_currentRenderingFaceID == LOGICAL_FACE_BOTTOM) {
                        if (source_logical_face_index_v == 0.0) { /* F -> Bo (Boの上端 vs Fの下端) */ conn_v_flip = true; }
                        else if (source_logical_face_index_v == 2.0) { /* B -> Bo (Boの下端 vs Bの下端) */ conn_v_flip = false; }
                    }

                    float u_after_connection_rules = u_src_raw; // Uフリップは行わない
                    float v_after_connection_rules = v_src_raw;

                    if (conn_v_flip) {
                        v_after_connection_rules = 1.0 - v_after_connection_rules;
                    }

                    // LED表示方向のためのV座標調整
                    float v_final_for_sampling = v_after_connection_rules;
                    if (u_invertVForLed) {
                        v_final_for_sampling = 1.0 - v_final_for_sampling;
                    }
                    
                    vec2 uv_for_sampling = vec2(u_after_connection_rules, v_final_for_sampling);

                    // bool apply_180_deg_rotation のロジックは削除またはコメントアウト
                    // if (apply_180_deg_rotation) {
                    //    uv_for_sampling = vec2(1.0 - uv_for_sampling.x, 1.0 - uv_for_sampling.y);
                    // }


                    float atlas_slot_v_scroll;
                    if (source_logical_face_index_v == 0.0) atlas_slot_v_scroll = float(ATLAS_SLOT_FRONT);
                    else if (source_logical_face_index_v == 1.0) atlas_slot_v_scroll = float(ATLAS_SLOT_TOP);
                    else if (source_logical_face_index_v == 2.0) atlas_slot_v_scroll = float(ATLAS_SLOT_BACK);
                    else if (source_logical_face_index_v == 3.0) atlas_slot_v_scroll = float(ATLAS_SLOT_BOTTOM);
                    else atlas_slot_v_scroll = float(ATLAS_SLOT_FRONT); // Fallback

                    vec2 slot_offset_v_scroll = vec2(atlas_slot_v_scroll / ATLAS_COLS, 0.0);
                    final_atlas_uv = slot_offset_v_scroll + uv_for_sampling * uv_scale_per_slot;

                } else { // LEFT, RIGHT 面 (Vスクロール対象外、面内回転のみ)
                     final_atlas_uv = default_slot_offset + uv_after_local_rotation * uv_scale_per_slot;
                }
            } else { // AXIS_Z, AXIS_NONE, またはその他の場合 (面内スクロールまたはスクロールなし)
                // Z軸回転の場合、u_scrollOffsetVec にPythonから面ごとのスクロール量が設定される。
                // AXIS_NONE の場合、u_scrollOffsetVec は (0,0)。
                // 面内回転後のUVに、さらに面内スクロールオフセットを加える。
                vec2 scrolled_uv_local = uv_after_local_rotation + u_scrollOffsetVec;
                // テクスチャパラメータ (GL_REPEAT等) によってラップアラウンドされる。
                final_atlas_uv = default_slot_offset + scrolled_uv_local * uv_scale_per_slot;
            }
            FragColor = texture(u_panoramaTexture, final_atlas_uv);
        }
        """
        self.program = self._compile_and_link_program(vertex_shader_src, fragment_shader_src)
        glUseProgram(self.program)

        tex_loc = glGetUniformLocation(self.program, "u_panoramaTexture")
        if (tex_loc != -1):
            glUniform1i(tex_loc, 0) # テクスチャユニット0
        else:
            print("Warning: u_panoramaTexture uniform not found.")

        scroll_offset_vec_loc = glGetUniformLocation(self.program, "u_scrollOffsetVec")
        if (scroll_offset_vec_loc != -1):
            glUniform2f(scroll_offset_vec_loc, 0.0, 0.0) # 初期値 (0,0)
        else:
            print("Warning: u_scrollOffsetVec uniform not found.")
        
        # u_rotationAxis のロケーションを取得し初期化
        rotation_axis_loc = glGetUniformLocation(self.program, "u_rotationAxis")
        if (rotation_axis_loc != -1):
            glUniform1i(rotation_axis_loc, self.ROTATION_AXIS_NONE) # 初期値は回転なし
        else:
            print("Warning: u_rotationAxis uniform not found.")

        print("Shaders initialized for 2D Panorama Texture with Axis-based rotation.")
        check_gl_error("Shader Program Use (Panorama with Axis Rotation)")

    def _init_buffers(self):
        # 各頂点に (x, y, z, u, v) の情報を持たせる
        # UV座標は各面の左下を(0,0)、右上を(1,1)とする
        vertices = np.array([
            # 前面 (Front) - Zが正
            -0.5, -0.5,  0.5,  0.0, 0.0, # 左下
             0.5, -0.5,  0.5,  1.0, 0.0, # 右下
             0.5,  0.5,  0.5,  1.0, 1.0, # 右上
            -0.5,  0.5,  0.5,  0.0, 1.0, # 左上

            # 背面 (Back) - Zが負
            -0.5, -0.5, -0.5,  1.0, 0.0,
            -0.5,  0.5, -0.5,  1.0, 1.0,
             0.5,  0.5, -0.5,  0.0, 1.0,
             0.5, -0.5, -0.5,  0.0, 0.0,

            # 上面 (Top) - Yが正 (U座標を反転)
            # V座標は前回修正済みと仮定 (例: 0.0, 0.0, 1.0, 1.0 の順)
            -0.5,  0.5, -0.5,  1.0, 0.0, # 元のUは0.0
            -0.5,  0.5,  0.5,  1.0, 1.0, # 元のUは0.0
             0.5,  0.5,  0.5,  0.0, 1.0, # 元のUは1.0
             0.5,  0.5, -0.5,  0.0, 0.0, # 元のUは1.0

            # 底面 (Bottom) - Yが負 (U座標を反転)
            # V座標は前回修正済みと仮定 (例: 1.0, 1.0, 0.0, 0.0 の順)
            -0.5, -0.5, -0.5,  1.0, 1.0, # 元のUは0.0
             0.5, -0.5, -0.5,  0.0, 1.0, # 元のUは1.0
             0.5, -0.5,  0.5,  0.0, 0.0, # 元のUは1.0
            -0.5, -0.5,  0.5,  1.0, 0.0, # 元のUは0.0


            # 右面 (Right) - Xが正
             0.5, -0.5, -0.5,  1.0, 0.0,
             0.5,  0.5, -0.5,  1.0, 1.0,
             0.5,  0.5,  0.5,  0.0, 1.0,
             0.5, -0.5,  0.5,  0.0, 0.0,

            # 左面 (Left) - Xが負
            -0.5, -0.5, -0.5,  0.0, 0.0,
            -0.5, -0.5,  0.5,  1.0, 0.0,
            -0.5,  0.5,  0.5,  1.0, 1.0,
            -0.5,  0.5, -0.5,  0.0, 1.0
        ], dtype=np.float32)

        # インデックスは変更なし (各面が4頂点で定義されるようになったため、
        # 以前の24頂点定義からインデックスも変わるべきだが、
        # ここでは簡略化のため、以前のインデックスを流用し、
        # 各面が2つの三角形で描画されるようにする。
        # ただし、UVの連続性を考えると、各面を独立した4頂点で定義し、
        # インデックスもそれに対応させるのがより正しい。)
        # 今回は、以前のインデックス構造を維持し、頂点データのみ変更する。
        # そのため、一部の面でUVが期待通りにならない可能性がある。
        # 正しくは、24頂点それぞれに固有のUVを設定し、インデックスもそれに合わせる。
        # ここでは、簡略化のため、各面ごとに4つの頂点を定義し、
        # インデックスもそれに対応するように変更する。
        indices = np.array([
             0,  1,  2,   2,  3,  0,  # Front
             4,  5,  6,   6,  7,  4,  # Back
             8,  9, 10,  10, 11,  8,  # Top
            12, 13, 14,  14, 15, 12, # Bottom
            16, 17, 18,  18, 19, 16, # Right
            20, 21, 22,  22, 23, 20  # Left
        ], dtype=np.uint16)
        self.indices_data = indices

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        self.vertex_buffer = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vertex_buffer)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # 位置属性 (location = 0)
        stride = 5 * vertices.itemsize # 3 floats for position + 2 floats for UV
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # UV属性 (location = 1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * vertices.itemsize))
        glEnableVertexAttribArray(1)

        self.element_buffer = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.element_buffer)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, self.indices_data.nbytes, self.indices_data, GL_STATIC_DRAW)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)

        print("Buffers (VBO, EBO, VAO) initialized with UVs.")
        check_gl_error("Buffer Init End")

    def set_panorama_texture(self, image: Image.Image):
        """単一の2Dテクスチャ (展開図など) を設定する。"""
        if image is None:
            raise ValueError("Input image for panorama texture is None.")

        if self.panorama_texture_id is None:
            self.panorama_texture_id = glGenTextures(1)
            print(f"Generated new Panorama texture ID: {self.panorama_texture_id}")

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.panorama_texture_id)
        check_gl_error("SetPanorama Bind")

        if image.mode != "RGB":
            image = image.convert("RGB")
        img_data = image.tobytes()

        if (image.width == 0 or image.height == 0):
            raise ValueError(f"Panorama image has zero dimension (size: {image.size}).")

        try:
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, image.width, image.height, 0, GL_RGB, GL_UNSIGNED_BYTE, img_data)
            print(f"Panorama texture set from image (size: {image.size})")
        except Exception as e:
            print(f"Error in glTexImage2D for panorama texture: {e}")
            glBindTexture(GL_TEXTURE_2D, 0)
            raise

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        # テクスチャラップモードを GL_MIRRORED_REPEAT に変更
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_MIRRORED_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_MIRRORED_REPEAT)
        check_gl_error("SetPanorama Params")

        glBindTexture(GL_TEXTURE_2D, 0)
        check_gl_error("SetPanorama Unbind")
        print("Panorama texture set successfully.")
        
    def render_face_to_fbo(self, face_id_to_render,
                       cube_global_rot_x, cube_global_rot_y, cube_global_rot_z,
                       texture_rotation_axis=ROTATION_AXIS_NONE,
                       texture_rotation_angle_deg=0):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.width, self.height)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glUseProgram(self.program)

        model_matrix = self._get_rotation_matrix(cube_global_rot_x, cube_global_rot_y, cube_global_rot_z)
        glUniformMatrix4fv(glGetUniformLocation(self.program, "model"), 1, GL_FALSE, model_matrix.T)
        view_matrix = self._get_face_view_matrix(face_id_to_render)
        glUniformMatrix4fv(glGetUniformLocation(self.program, "view"), 1, GL_FALSE, view_matrix.T)
        projection_matrix = self._get_orthographic_projection_matrix(-0.5, 0.5, -0.5, 0.5, 0.1, 10.0)
        glUniformMatrix4fv(glGetUniformLocation(self.program, "projection"), 1, GL_FALSE, projection_matrix.T)

        current_texture_rot_for_face = 0.0
        scroll_offset_u = 0.0
        scroll_offset_v = 0.0
        invert_v_for_led = False # LED表示のV方向を反転させるかどうかのフラグ

        if texture_rotation_axis == self.ROTATION_AXIS_X:
            # テクスチャ供給源のスクロール: 「下から上へ」(FRONT -> BOTTOM -> BACK -> TOP)
            # texture_rotation_angle_deg が増加すると scroll_offset_v は負の方向に増加
            scroll_offset_v = -(texture_rotation_angle_deg / 360.0) * 4.0

            # 各面のLED表示方向の制御
            if face_id_to_render == self.FACE_FRONT:
                # FRONT面はLED「上から下へ」表示
                # scroll_offset_v が負だと v_on_selected_logical_face は 0.9->0.0 (下から上)
                # なので反転して 0.0->0.9 (上から下へ) にする
                invert_v_for_led = True
            elif face_id_to_render == self.FACE_TOP:
                # TOP面の希望: ここでは仮に「上から下へ」とする
                invert_v_for_led = True
            elif face_id_to_render == self.FACE_BACK:
                # BACK面の希望: ここでは仮に「上から下へ」とする
                invert_v_for_led = True
            elif face_id_to_render == self.FACE_BOTTOM:
                # BOTTOM面の希望: ここでは仮に「上から下へ」とする
                invert_v_for_led = True
            
            # L/R面の面内回転
            if face_id_to_render == self.FACE_LEFT: current_texture_rot_for_face = -texture_rotation_angle_deg
            elif face_id_to_render == self.FACE_RIGHT: current_texture_rot_for_face = texture_rotation_angle_deg
        elif texture_rotation_axis == self.ROTATION_AXIS_Y:
            # Y軸回転の場合のUスクロールと面内回転 (invert_u_for_led も同様に検討可能)
            if face_id_to_render in [self.FACE_FRONT, self.FACE_RIGHT, self.FACE_BACK, self.FACE_LEFT]:
                # 仮にUスクロール方向は F->R->B->L (正方向)
                scroll_offset_u = (texture_rotation_angle_deg / 360.0) * 4.0
                # ここでも invert_u_for_led のようなフラグでLED表示方向を制御できる
            if face_id_to_render == self.FACE_TOP: current_texture_rot_for_face = texture_rotation_angle_deg
            elif face_id_to_render == self.FACE_BOTTOM: current_texture_rot_for_face = -texture_rotation_angle_deg
        elif texture_rotation_axis == self.ROTATION_AXIS_Z:
            # Z軸回転の場合の面内スクロールと面内回転
            scroll_amount = (texture_rotation_angle_deg / 360.0) # Z軸は1面分でラップアラウンド想定
            if face_id_to_render == self.FACE_RIGHT: scroll_offset_v = -scroll_amount # 例: 上へ
            elif face_id_to_render == self.FACE_TOP: scroll_offset_u = scroll_amount   # 例: 右へ
            elif face_id_to_render == self.FACE_LEFT: scroll_offset_v = scroll_amount  # 例: 下へ
            elif face_id_to_render == self.FACE_BOTTOM: scroll_offset_u = -scroll_amount # 例: 左へ
            if face_id_to_render == self.FACE_FRONT: current_texture_rot_for_face = texture_rotation_angle_deg
            elif face_id_to_render == self.FACE_BACK: current_texture_rot_for_face = -texture_rotation_angle_deg

        texture_transform_matrix = self._get_texture_transform_matrix(current_texture_rot_for_face)
        tex_transform_loc = glGetUniformLocation(self.program, "u_textureTransform")
        if (tex_transform_loc != -1):
            glUniformMatrix3fv(tex_transform_loc, 1, GL_FALSE, texture_transform_matrix.T.flatten())

        scroll_offset_loc = glGetUniformLocation(self.program, "u_scrollOffsetVec")
        if (scroll_offset_loc != -1):
            glUniform2f(scroll_offset_loc, scroll_offset_u, scroll_offset_v)
        else:
            print("Warning: u_scrollOffsetVec uniform not found.")

        # u_invertVForLed uniform を設定
        invert_v_loc = glGetUniformLocation(self.program, "u_invertVForLed")
        if (invert_v_loc != -1):
            glUniform1i(invert_v_loc, 1 if invert_v_for_led else 0) # boolをintとして渡す
        else:
            print("Warning: u_invertVForLed uniform not found.")

        current_face_id_loc = glGetUniformLocation(self.program, "u_currentRenderingFaceID")
        if (current_face_id_loc != -1):
            glUniform1i(current_face_id_loc, face_id_to_render)
        else:
            print(f"Warning: u_currentRenderingFaceID uniform not found for face {face_id_to_render}")

        # u_rotationAxis に現在の回転軸を設定
        rotation_axis_loc = glGetUniformLocation(self.program, "u_rotationAxis")
        if (rotation_axis_loc != -1):
            glUniform1i(rotation_axis_loc, texture_rotation_axis)
        else:
            print("Warning: u_rotationAxis uniform not found.")

        glActiveTexture(GL_TEXTURE0)
        if (self.panorama_texture_id is not None):
            glBindTexture(GL_TEXTURE_2D, self.panorama_texture_id)
        else:
            glBindTexture(GL_TEXTURE_2D, 0)
        check_gl_error(f"RenderFaceToFBO Activate & Bind Panorama Texture (Face {face_id_to_render})")

        glBindVertexArray(self.vao)
        glDrawElements(GL_TRIANGLES, len(self.indices_data), GL_UNSIGNED_SHORT, None)
        glBindVertexArray(0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glUseProgram(0)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        check_gl_error(f"RenderFaceToFBO Unbind All & End (Face {face_id_to_render})")

    def _get_texture_transform_matrix(self, angle_y_deg):
        """
        2Dテクスチャ変換行列（3x3）を生成する。
        テクスチャの中心 (0.5, 0.5) を軸にY軸周り（UV空間ではU軸周りやV軸周りに相当する回転）の回転を行う。
        ここでは簡単のため、2D平面上での回転とする。
        angle_y_deg: テクスチャを回転させる角度（度数法）
        """
        center_x, center_y = 0.5, 0.5
        rad = np.radians(angle_y_deg) # Y軸回転を2Dの回転角として扱う
        cos_a = np.cos(rad)
        sin_a = np.sin(rad)

        # 1. 中心への平行移動
        translate_to_origin = np.array([
            [1, 0, -center_x],
            [0, 1, -center_y],
            [0, 0, 1]
        ], dtype=np.float32)

        # 2. 回転
        rotation = np.array([
            [cos_a, -sin_a, 0],
            [sin_a,  cos_a, 0],
            [0,      0,     1]
        ], dtype=np.float32)

        # 3. 元の位置への平行移動
        translate_back = np.array([
            [1, 0, center_x],
            [0, 1, center_y],
            [0, 0, 1]
        ], dtype=np.float32)

        # 変換行列を合成: T_back * R * T_origin
        transform_matrix = translate_back @ rotation @ translate_to_origin
        return transform_matrix
    
    def render_cube_to_stitched_image(self,
                                      texture_rotation_axis=ROTATION_AXIS_NONE,
                                      texture_rotation_angle_deg=0):
        if not self.face_order_ids_for_stitch:
            print("警告: face_order_ids_for_stitch が設定されていません。")
            return None
        if self.panorama_texture_id is None: # cubemap_texture_id から変更
            print("警告: パノラマテクスチャが設定されていません。set_panorama_texture()を呼び出してください。")
            dummy_face = Image.new('RGB', (self.width, self.height), 'red')
            stitched_image_width = self.width * len(self.face_order_ids_for_stitch)
            stitched_image_height = self.height
            stitched_image = Image.new('RGB', (stitched_image_width, stitched_image_height))
            for i in range(len(self.face_order_ids_for_stitch)):
                 stitched_image.paste(dummy_face, (i * self.width, 0))
            return stitched_image
        # ... (以降のロジックはほぼ同じ) ...
        stitched_image_width = self.width * len(self.face_order_ids_for_stitch)
        stitched_image_height = self.height
        stitched_image = Image.new('RGB', (stitched_image_width, stitched_image_height))

        cube_global_rot_x = 0.0
        cube_global_rot_y = 0.0
        cube_global_rot_z = 0.0

        for i, face_id_to_render in enumerate(self.face_order_ids_for_stitch):
            self.render_face_to_fbo(face_id_to_render,
                                    cube_global_rot_x, cube_global_rot_y, cube_global_rot_z,
                                    texture_rotation_axis, texture_rotation_angle_deg)
            face_image = self.get_image_from_fbo()

            if face_image:
                stitched_image.paste(face_image, (i * self.width, 0))
            else:
                print(f"警告: face_id {face_id_to_render} のレンダリング結果がNoneです。")
                placeholder = Image.new('RGB', (self.width, self.height), 'magenta')
                stitched_image.paste(placeholder, (i * self.width, 0))
        
        return stitched_image

    def _compile_and_link_program(self, vertex_source, fragment_source):
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
    def cleanup(self):
        if self.cleaned_up:
            return
        print("Cleaning up HeadlessCubeRenderer resources...")
        if self.fbo: glDeleteFramebuffers(1, [self.fbo]); self.fbo = None
        if self.fbo_texture: glDeleteTextures(1, [self.fbo_texture]); self.fbo_texture = None
        if self.panorama_texture_id: glDeleteTextures(1, [self.panorama_texture_id]); self.panorama_texture_id = None # cubemap_texture_id から変更
        if self.program: glDeleteProgram(self.program); self.program = None
        if self.vao: glDeleteVertexArrays(1, [self.vao]); self.vao = None
        if self.element_buffer: glDeleteBuffers(1, [self.element_buffer]); self.element_buffer = None
        if self.vertex_buffer: glDeleteBuffers(1, [self.vertex_buffer]); self.vertex_buffer = None

        if self.glut_window_id is not None:
            # glutDestroyWindow(self.glut_window_id) # コンテキストに注意
            self.glut_window_id = None

        self.cleaned_up = True
        print("HeadlessCubeRenderer resources cleaned up.")

    def _get_rotation_matrix(self, angle_x, angle_y, angle_z):
        """キューブ全体の回転のための4x4行列を生成する。"""
        rad_x = np.radians(angle_x)
        cos_x, sin_x = np.cos(rad_x), np.sin(rad_x)
        rot_x = np.array([[1,0,0,0], [0,cos_x,-sin_x,0], [0,sin_x,cos_x,0], [0,0,0,1]], dtype=np.float32)
        
        rad_y = np.radians(angle_y)
        cos_y, sin_y = np.cos(rad_y), np.sin(rad_y)
        rot_y = np.array([[cos_y,0,sin_y,0], [0,1,0,0], [-sin_y,0,cos_y,0], [0,0,0,1]], dtype=np.float32)
        
        rad_z = np.radians(angle_z)
        cos_z, sin_z = np.cos(rad_z), np.sin(rad_z)
        rot_z = np.array([[cos_z,-sin_z,0,0], [sin_z,cos_z,0,0], [0,0,1,0], [0,0,0,1]], dtype=np.float32)
        
        return rot_z @ rot_y @ rot_x # ZYX order

    def _get_face_view_matrix(self, face_id):
        """指定された面をカメラの正面に向けるためのビュー行列を生成する。"""
        eye = np.array([0.0, 0.0, 0.0]) 
        center = np.array([0.0, 0.0, 0.0]) 
        up = np.array([0.0, 1.0, 0.0]) 

        dist = 1.0 
        # OpenGLの標準的なキューブマップ座標系を意識した視点設定
        # +X: Right, -X: Left, +Y: Top, -Y: Bottom, +Z: Front, -Z: Back
        if face_id == self.FACE_FRONT:   eye = np.array([0.0, 0.0,  dist]); up = np.array([0,1,0]) # Look at +Z
        elif face_id == self.FACE_BACK:  eye = np.array([0.0, 0.0, -dist]); up = np.array([0,1,0]) # Look at -Z
        elif face_id == self.FACE_TOP:   eye = np.array([0.0,  dist, 0.0]); up = np.array([0,0,1]) # Look at +Y, Z+ is up for texture
        elif face_id == self.FACE_BOTTOM:eye = np.array([0.0, -dist, 0.0]); up = np.array([0,0,-1])# Look at -Y, Z- is up for texture
        elif face_id == self.FACE_RIGHT: eye = np.array([ dist, 0.0, 0.0]); up = np.array([0,1,0]) # Look at +X
        elif face_id == self.FACE_LEFT:  eye = np.array([-dist, 0.0, 0.0]); up = np.array([0,1,0]) # Look at -X
        else:
            raise ValueError(f"Invalid face_id: {face_id}")

        # Standard LookAt matrix calculation (simplified: camera always at origin, target moves)
        # For FBO rendering of faces, it's easier to position the camera
        z_axis = (eye - center) / np.linalg.norm(eye - center) if np.linalg.norm(eye - center) > 1e-6 else np.array([0,0,1])
        x_axis = np.cross(up, z_axis)
        x_axis = x_axis / np.linalg.norm(x_axis) if np.linalg.norm(x_axis) > 1e-6 else np.array([1,0,0])
        y_axis = np.cross(z_axis, x_axis)
        
        # Transpose of the rotation part of a camera matrix
        rotation = np.identity(4, dtype=np.float32)
        rotation[0,0:3] = x_axis
        rotation[1,0:3] = y_axis
        rotation[2,0:3] = z_axis
        
        # Translation part of a camera matrix
        translation = np.identity(4, dtype=np.float32)
        translation[0,3] = -np.dot(x_axis, eye)
        translation[1,3] = -np.dot(y_axis, eye)
        translation[2,3] = -np.dot(z_axis, eye)
        
        return translation @ rotation # More standard view matrix calculation: V = T * R


    def _get_orthographic_projection_matrix(self, left, right, bottom, top, near, far):
        """正射影行列を生成する。"""
        projection_matrix = np.zeros((4,4), dtype=np.float32)
        projection_matrix[0,0] = 2.0 / (right - left)
        projection_matrix[1,1] = 2.0 / (top - bottom)
        projection_matrix[2,2] = -2.0 / (far - near) # OpenGLは右手座標系なので -2.0
        projection_matrix[3,3] = 1.0
        projection_matrix[0,3] = -(right + left) / (right - left)
        projection_matrix[1,3] = -(top + bottom) / (top - bottom)
        projection_matrix[2,3] = -(far + near) / (far - near)
        return projection_matrix

    def __del__(self):
        # __del__ でのOpenGLリソース解放はコンテキストの問題で不安定なため非推奨
        # 利用側で明示的に cleanup() を呼び出すことを強く推奨
        if not self.cleaned_up:
             print(f"Warning: HeadlessCubeRenderer instance {id(self)} being deleted without explicit cleanup call.")
             # self.cleanup() # ここで呼ぶと問題が起きやすい

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

        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE):
            status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
            raise RuntimeError(f"Framebuffer is not complete! Status: {status}")

        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        print("FBO initialized successfully.")
        check_gl_error("FBO Init End")

    def _get_texture_rotation_matrix(self, angle_x, angle_y, angle_z):
        """テクスチャ回転用の4x4行列を生成する。"""
        # _get_rotation_matrix と同じロジックで回転行列を生成
        rad_x = np.radians(angle_x)
        cos_x, sin_x = np.cos(rad_x), np.sin(rad_x)
        rot_x = np.array([[1,0,0,0], [0,cos_x,-sin_x,0], [0,sin_x,cos_x,0], [0,0,0,1]], dtype=np.float32)
        
        rad_y = np.radians(angle_y)
        cos_y, sin_y = np.cos(rad_y), np.sin(rad_y)
        rot_y = np.array([[cos_y,0,sin_y,0], [0,1,0,0], [-sin_y,0,cos_y,0], [0,0,0,1]], dtype=np.float32)
        
        rad_z = np.radians(angle_z)
        cos_z, sin_z = np.cos(rad_z), np.sin(rad_z)
        rot_z = np.array([[cos_z,-sin_z,0,0], [sin_z,cos_z,0,0], [0,0,1,0], [0,0,0,1]], dtype=np.float32)
        
        # 回転の順序はテクスチャ座標系での挙動によって調整が必要な場合がある
        return rot_z @ rot_y @ rot_x # ZYX order (一般的なオブジェクト回転と同じ)


    def get_image_from_fbo(self) -> Image.Image:
        """FBOから現在のレンダリング結果を画像として取得する。"""
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glReadBuffer(GL_COLOR_ATTACHMENT0)
        pixels = glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE)
        check_gl_error("Read Pixels from FBO")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        image = Image.frombytes("RGB", (self.width, self.height), pixels)
        # FBOから読み取った画像は上下反転していることがあるので、必要なら反転
        # image = image.transpose(Image.FLIP_TOP_BOTTOM)
        return image