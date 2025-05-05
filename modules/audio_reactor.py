import sounddevice as sd
import numpy as np
import queue
import sys
import time
from collections import deque

DEVICE_NAME = 'pulse'
SAMPLE_RATE = 48000
CHANNELS = 2         # モニタソースは通常ステレオ
BLOCK_DURATION_MS = 50 # 処理する音声チャンクのミリ秒
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION_MS / 1000) # 1ブロックのフレーム数

# --- ビート検出パラメータ (各帯域 - 要調整) ---
# 周波数帯域の定義 (Hz) - ここは音楽や検出したい音に合わせて調整
FREQ_BANDS = {
    "Bass":   (50, 150),     # 低域 (キックなど)
    "Mid":    (500, 2000),   # 中域 (スネア、ボーカルの一部など)
    "Treble": (4000, 10000), # 高域 (ハイハット、シンバルなど)
}

# 各帯域共通の履歴長 (個別に設定も可能)
HISTORY_LEN = 15

# 各帯域の閾値比率 (値が大きいほど鈍感になる)
THRESHOLD_RATIO = {
    "Bass":   2.0,
    "Mid":    2.5,
    "Treble": 3.0,
}

# 各帯域の最小エネルギー閾値 (無音時の誤検出防止)
MIN_ENERGY_THRESHOLD = {
    "Bass":   1e-6,
    "Mid":    5e-7, # 中高域はエネルギーが小さいことが多いので調整
    "Treble": 1e-7,
}

# 各帯域のクールダウンブロック数
COOLDOWN_BLOCKS = {
    "Bass":   4,
    "Mid":    3,
    "Treble": 2,
}

# --- FFT関連の前計算 ---
try:
    # FFT結果の各ビンに対応する周波数リスト
    freqs = np.fft.rfftfreq(BLOCK_SIZE, 1.0 / SAMPLE_RATE)
    # 各帯域に対応するFFTインデックスを事前に計算
    band_indices = {}
    valid_bands = {} # 有効だった帯域名と範囲を格納
    print("--- Frequency Band Setup ---")
    for name, (low, high) in FREQ_BANDS.items():
        indices = np.where((freqs >= low) & (freqs <= high))[0]
        if len(indices) > 0:
            band_indices[name] = indices
            valid_bands[name] = (low, high)
            print(f"  {name:>6s}: {low:5d}-{high:5d} Hz (Indices: {indices[0]:>4d}-{indices[-1]:>4d})")
        else:
            # もし指定帯域にFFTビンが存在しない場合は警告
            print(f"  Warning: Band '{name}' ({low}-{high} Hz) has no corresponding FFT bins.")
    if not valid_bands:
        print("エラー: 有効な周波数帯域がありません。設定を確認してください。")
        sys.exit(1)
    # 無効な帯域を除いたもので上書き
    FREQ_BANDS = valid_bands
    print("-----------------------------")

except ValueError as e:
    print(f"FFT関連の計算でエラー: {e}")
    print("SAMPLE_RATE または BLOCK_DURATION_MS の設定を確認してください。")
    sys.exit(1)
except Exception as e:
    print(f"FFT前計算で予期せぬエラー: {e}")
    sys.exit(1)


# --- グローバル変数 (帯域ごとに用意) ---
q = queue.Queue()
# 各帯域のエネルギー履歴を保持する辞書
energy_histories = {name: deque(maxlen=HISTORY_LEN) for name in FREQ_BANDS.keys()}
# 各帯域のクールダウンカウンターを保持する辞書
beat_cooldown_counters = {name: 0 for name in FREQ_BANDS.keys()}

def audio_callback(indata, frames, time, status):
    """オーディオ入力コールバック関数: 音声データをキューに入れる"""
    if status:
        print(status, file=sys.stderr)
    q.put(indata.copy())

def detect_beats_frequency(audio_chunk):
    """音声チャンクから各周波数帯域のビート(エネルギー上昇)を検出する関数"""
    global beat_cooldown_counters, energy_histories

    # 検出結果を格納する辞書 (例: {"Bass": True, "Mid": False, ...})
    detected_beats = {name: False for name in FREQ_BANDS.keys()}

    # --- 1. FFT 計算 (全帯域共通) ---
    # ステレオの場合はモノラルに変換
    if CHANNELS > 1:
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
    for name in FREQ_BANDS.keys():
        # この帯域に対応するインデックスを取得
        indices = band_indices[name]

        # この帯域のエネルギーを計算 (振幅の合計)
        current_band_energy = np.sum(amplitude_spectrum[indices])

        # 履歴と比較してビート判定
        avg_energy = 0.0
        # 履歴が十分溜まっていれば平均を計算
        if len(energy_histories[name]) == HISTORY_LEN:
            avg_energy = np.mean(energy_histories[name])

        # ビート判定ロジック
        if beat_cooldown_counters[name] == 0 and \
           len(energy_histories[name]) == HISTORY_LEN and \
           current_band_energy > avg_energy * THRESHOLD_RATIO[name] and \
           current_band_energy > MIN_ENERGY_THRESHOLD[name]:

            detected_beats[name] = True # この帯域でビート検出
            beat_cooldown_counters[name] = COOLDOWN_BLOCKS[name] # クールダウン開始

            # --- ビート検出時のアクション ---
            print(f"Beat ({name:>6s})! E:{current_band_energy:.3f}")
            # ここで帯域名(name)に応じてLEDの色を変えるなどの処理
            # 例: control_led(band_name=name, state=True)
            # ---------------------------------

        # 履歴を更新
        energy_histories[name].append(current_band_energy)

        # クールダウンカウンターを減らす
        if beat_cooldown_counters[name] > 0:
            beat_cooldown_counters[name] -= 1
        # elif not detected_beats[name]: # ビートが検出されず、クールダウン中でもない場合
             # 例: control_led(band_name=name, state=False)

    return detected_beats # 各帯域の検出結果 (True/False) を含む辞書を返す

# --- メイン実行部 ---
if __name__ == "__main__":
    # --- 初期化 ---
    # 各帯域の履歴をゼロで初期化
    for name in FREQ_BANDS.keys():
        for _ in range(HISTORY_LEN):
            energy_histories[name].append(0.0)

    try:
        # --- ストリーム開始 ---
        print(f"Attempting to use input device: {DEVICE_NAME}")
        print(f"Sample Rate: {SAMPLE_RATE}, Channels: {CHANNELS}, Block Size: {BLOCK_SIZE}")

        stream = sd.InputStream(
            device=DEVICE_NAME,
            channels=CHANNELS,
            samplerate=SAMPLE_RATE,
            callback=audio_callback,
            blocksize=BLOCK_SIZE
        )

        print("Audio stream started... Press Ctrl+C to stop.")
        with stream:
            # --- メインループ: キューからデータを取り出して処理 ---
            while True:
                try:
                    audio_chunk = q.get(timeout=0.1)
                    detected_beats_in_bands = detect_beats_frequency(audio_chunk)

                    # --- 検出結果を使った処理 ---
                    # 例: 各帯域の検出結果に応じて何かする
                    # if detected_beats_in_bands["Bass"]:
                    #     print("Bass Hit!")
                    # if detected_beats_in_bands["Mid"]:
                    #     print("Mid Hit!")
                    # if detected_beats_in_bands["Treble"]:
                    #     print("Treble Hit!")
                    # ---------------------------

                except queue.Empty:
                    # キューが空でも問題ない
                    time.sleep(0.01) # CPU負荷軽減

    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if "Invalid device" in str(e) or "No such device" in str(e) or "Device unavailable" in str(e):
            print("\n--- Available input devices ---")
            try:
                print(sd.query_devices())
            except Exception as sd_err:
                print(f"Could not query devices: {sd_err}")
            print("-------------------------------")
            print(f"Error: Input device '{DEVICE_NAME}' not found or unavailable.")
        sys.exit(1)
    finally:
        print()