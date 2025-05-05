import sounddevice as sd
import numpy as np
import queue
import sys
import time
from collections import deque

class AudioReactor:
    """音声からビートを検出するためのクラス"""
    
    def __init__(self, 
                 device_name='pulse',
                 sample_rate=48000,
                 channels=2,
                 block_duration_ms=50,
                 freq_bands=None,
                 history_len=15,
                 threshold_ratio=None,
                 min_energy_threshold=None,
                 cooldown_blocks=None):
        """
        AudioReactorの初期化
        
        Args:
            device_name: オーディオ入力デバイス名
            sample_rate: サンプリングレート (Hz)
            channels: チャネル数
            block_duration_ms: 処理ブロックサイズ (ミリ秒)
            freq_bands: 周波数帯域辞書 {'名前': (最小Hz, 最大Hz)}
            history_len: 履歴長
            threshold_ratio: 閾値比率辞書 {'名前': 比率}
            min_energy_threshold: 最小エネルギー閾値辞書 {'名前': 閾値}
            cooldown_blocks: クールダウンブロック数辞書 {'名前': ブロック数}
        """
        # オーディオ設定
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_duration_ms = block_duration_ms
        self.block_size = int(self.sample_rate * self.block_duration_ms / 1000)
        
        # 周波数帯域の設定（デフォルト値またはカスタム値）
        self.freq_bands = freq_bands or {
            "Bass":   (50, 100),     # 低域 (キックなど)
            "Mid":    (500, 2000),   # 中域 (スネア、ボーカルの一部など)
            "Treble": (4000, 10000), # 高域 (ハイハット、シンバルなど)
        }
        
        # ビート検出パラメータ
        self.history_len = history_len
        self.threshold_ratio = threshold_ratio or {
            "Bass":   2.0,
            "Mid":    2.5,
            "Treble": 3.0,
        }
        self.min_energy_threshold = min_energy_threshold or {
            "Bass":   1e-2,
            "Mid":    5e-7,
            "Treble": 1e-7,
        }
        self.cooldown_blocks = cooldown_blocks or {
            "Bass":   4,
            "Mid":    3,
            "Treble": 2,
        }
        
        # ストリーム制御
        self.stream = None
        self.is_running = False
        
        # データキューとビート検出状態の初期化
        self.q = queue.Queue()
        self.energy_histories = {}
        self.beat_cooldown_counters = {}
        self.band_indices = {}
        self.valid_bands = {}
        
        # FFT関連の前計算
        self._setup_fft()
        
        # 各帯域の履歴を初期化
        self._initialize_histories()
    
    def _setup_fft(self):
        """FFT関連の前計算を行う"""
        try:
            # FFT結果の各ビンに対応する周波数リスト
            self.freqs = np.fft.rfftfreq(self.block_size, 1.0 / self.sample_rate)
            
            # 各帯域に対応するFFTインデックスを事前に計算
            print("--- Frequency Band Setup ---")
            for name, (low, high) in self.freq_bands.items():
                indices = np.where((self.freqs >= low) & (self.freqs <= high))[0]
                if len(indices) > 0:
                    self.band_indices[name] = indices
                    self.valid_bands[name] = (low, high)
                    print(f"  {name:>6s}: {low:5d}-{high:5d} Hz (Indices: {indices[0]:>4d}-{indices[-1]:>4d})")
                else:
                    print(f"  Warning: Band '{name}' ({low}-{high} Hz) has no corresponding FFT bins.")
            
            if not self.valid_bands:
                print("エラー: 有効な周波数帯域がありません。設定を確認してください。")
                raise ValueError("No valid frequency bands")
                
            # 無効な帯域を除いたもので上書き
            self.freq_bands = self.valid_bands
            print("-----------------------------")
            
        except ValueError as e:
            print(f"FFT関連の計算でエラー: {e}")
            print("SAMPLE_RATE または BLOCK_DURATION_MS の設定を確認してください。")
            raise
        except Exception as e:
            print(f"FFT前計算で予期せぬエラー: {e}")
            raise
    
    def _initialize_histories(self):
        """各帯域のエネルギー履歴とクールダウンカウンターを初期化"""
        self.energy_histories = {name: deque(maxlen=self.history_len) for name in self.freq_bands.keys()}
        self.beat_cooldown_counters = {name: 0 for name in self.freq_bands.keys()}
        
        # 各帯域の履歴をゼロで初期化
        for name in self.freq_bands.keys():
            for _ in range(self.history_len):
                self.energy_histories[name].append(0.0)
    
    def audio_callback(self, indata, frames, time, status):
        """オーディオ入力コールバック関数: 音声データをキューに入れる"""
        if status:
            print(status, file=sys.stderr)
        self.q.put(indata.copy())
    
    def detect_beats(self, audio_chunk):
        """音声チャンクから各周波数帯域のビート(エネルギー上昇)を検出する関数"""
        # 検出結果を格納する辞書 (例: {"Bass": True, "Mid": False, ...})
        detected_beats = {name: False for name in self.freq_bands.keys()}
        
        # --- 1. FFT 計算 (全帯域共通) ---
        # ステレオの場合はモノラルに変換
        if self.channels > 1:
            mono_chunk = np.mean(audio_chunk, axis=1)
        else:
            mono_chunk = audio_chunk[:, 0]
        
        # ハニング窓を適用
        window = np.hanning(len(mono_chunk))
        mono_chunk_windowed = mono_chunk * window
        
        # FFT を実行し、振幅スペクトルを取得
        fft_result = np.fft.rfft(mono_chunk_windowed)
        amplitude_spectrum = np.abs(fft_result)
        
        # --- 2 & 3. 各帯域でエネルギー計算と比較、判定 ---
        for name in self.freq_bands.keys():
            # この帯域に対応するインデックスを取得
            indices = self.band_indices[name]
            
            # この帯域のエネルギーを計算 (振幅の合計)
            current_band_energy = np.sum(amplitude_spectrum[indices])
            
            # 履歴と比較してビート判定
            avg_energy = 0.0
            # 履歴が十分溜まっていれば平均を計算
            if len(self.energy_histories[name]) == self.history_len:
                avg_energy = np.mean(self.energy_histories[name])
            
            # ビート判定ロジック
            if self.beat_cooldown_counters[name] == 0 and \
               len(self.energy_histories[name]) == self.history_len and \
               current_band_energy > avg_energy * self.threshold_ratio[name] and \
               current_band_energy > self.min_energy_threshold[name]:
                
                detected_beats[name] = True # この帯域でビート検出
                self.beat_cooldown_counters[name] = self.cooldown_blocks[name] # クールダウン開始
                
                # ビート検出時のログ
                print(f"Beat ({name:>6s})! E:{current_band_energy:.3f}")
                
            # 履歴を更新
            self.energy_histories[name].append(current_band_energy)
            
            # クールダウンカウンターを減らす
            if self.beat_cooldown_counters[name] > 0:
                self.beat_cooldown_counters[name] -= 1
        
        return detected_beats
    
    def start(self):
        """オーディオストリームを開始する"""
        if self.is_running:
            print("AudioReactor is already running")
            return False
        
        try:
            print(f"Attempting to use input device: {self.device_name}")
            print(f"Sample Rate: {self.sample_rate}, Channels: {self.channels}, Block Size: {self.block_size}")
            
            self.stream = sd.InputStream(
                device=self.device_name,
                channels=self.channels,
                samplerate=self.sample_rate,
                callback=self.audio_callback,
                blocksize=self.block_size
            )
            self.stream.start()
            self.is_running = True
            print("Audio stream started.")
            return True
            
        except Exception as e:
            print(f"Error starting AudioReactor: {e}")
            if "Invalid device" in str(e) or "No such device" in str(e) or "Device unavailable" in str(e):
                print(f"Audio device '{self.device_name}' not found or unavailable")
                try:
                    devices_info = sd.query_devices()
                    print("Available audio devices:")
                    for i, dev in enumerate(devices_info):
                        print(f"[{i}] {dev['name']}")
                except Exception as dev_err:
                    print(f"Could not query audio devices: {dev_err}")
            return False
    
    def stop(self):
        """オーディオストリームを停止する"""
        if not self.is_running:
            print("AudioReactor is not running")
            return
        
        print("Stopping AudioReactor...")
        self.is_running = False
        
        # オーディオストリームを停止
        if self.stream and self.stream.active:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        
        print("AudioReactor stopped")
    
    def get_audio_chunk(self, timeout=0.1):
        """キューから音声チャンクを取得する"""
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None