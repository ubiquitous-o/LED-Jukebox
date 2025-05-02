# LED-Jukebox

## Hardware Specifications
- Raspberry Pi 4B, 64GB microSD, Raspberry pi os lite(64-bit)
- [P2.5 64x64 RGB LED Matrix Panel](https://www.amazon.co.jp/dp/B07PK5J21V?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_2&th=1) x 5    
- [5V 40A Power Supply](https://www.amazon.co.jp/dp/B0B74KV3BB?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1&th=1)
- [8Ω 10W Speaker](https://akizukidenshi.com/catalog/g/g116600/) x4
- [10W+10W Stereo USB DAC Amplifier](https://akizukidenshi.com/catalog/g/g102404/)


## Dependencies
- [Raspotify](https://github.com/dtcooper/raspotify): Streams Spotify music using an open-source client for Spotify Connect on Raspberry Pi.
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix): Used for controlling the LED panels.

## Setup
1. Install Raspotify as a User Service for using Audio Reactive Scripts.
    - Install Raspotify.
    - Stop and Disable.
        - `sudo systemctl stop raspotify.service`
        - `sudo systemctl disable raspotify.service`
    - Create User Service.
        - `mkdir -p ~/.config/systemd/user/`
        - `mkdir -p ~/.cache/raspotify`
        - `vim ~/.config/systemd/user/raspotify.service`
            ```
            [Unit]
            Description=Raspotify (Spotify Connect Client - User Service for %u)
            # PipeWireが起動した後に開始するように依存関係を設定
            After=network.target sound.target pipewire.service pipewire-pulse.service
            Requires=pipewire.service pipewire-pulse.service
            
            [Service]
            # Raspotify がインストールした librespot を使用
            # パスは which librespot で確認可
            ExecStart=/usr/bin/librespot \
                --name "Raspi-%u" \
                --bitrate 320 \
                --cache "%h/.cache/raspotify" \
                --enable-volume-normalisation
                # --- 他に必要なオプションがあればここに追加 ---
                # 例: --username YOUR_USERNAME --password YOUR_PASSWORD
            
            Restart=always
            RestartSec=5
            
            [Install]
            WantedBy=default.target
            ```
        - `systemctl --user daemon-reload`
        - `systemctl --user enable raspotify.service`
        - `systemctl --user start raspotify.service`
    - Set Your Speaker.
        - `wpctl status`
        - Remenber your Sinks ID
        - `DEFAULT_SINK_ID=<your id>`
        - `NODE_NAME=$(pw-cli info $DEFAULT_SINK_ID | grep 'node.name = ' | head -n 1 | cut -d '"' -f 2)`
        - `MONITOR_SOURCE_NAME="${NODE_NAME}.monitor"`
           - example: `MONITOR_SOURCE_NAME="alsa_output.usb-Apple_Computer__Inc._Speakers_p4000-00.analog-stereo.monitor"`
          
    - Check for Playing and Recording at the Same Time.
        - Play spotify music on raspi using Spotify Connect
        - Record playing music
            - `PULSE_SOURCE=$MONITOR_SOURCE_NAME arecord -D pulse -r 48000 -f S16_LE -c 2 output.wav`
        
    - Set `handler.sh` as a Librespot Event Script
    - https://github.com/dtcooper/raspotify/wiki/How-To:-Listen-To-Librespot-Events
2. Install rpi-rgb-led-matrix
    - Refer to this guide to install the Python bindings: [python bindings](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python)
    - Install `rpi-rgb-led-matrix` into your venv:
        ```bash
        source venv/bin/activate
        cd rpi-rgb-led-matrix/bindings/python
        pip install .
        ```

