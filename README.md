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
1. Clone this repository.
    - `cd /usr/local/bin`
    - `git clone --recursive https://github.com/ubiquitous-o/LED-Jukebox.git`
    - venv install**あとで**
    - Set your `.env` file in `/usr/local/bin/LED-Jukebox/.env`.
      - Get your Spotify API credentials from [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
        ```
        SPOTIFY_CLIENT_ID=<your client id>
        SPOTIFY_SECRET_KEY=<your secret key>
        ```

2. Install Raspotify as a User Service for using Audio Reactive Scripts.
    - Install Raspotify.
        - `sudo apt-get -y install curl && curl -sL https://dtcooper.github.io/raspotify/install.sh | sh`
        - Install some audio libraries.
            - `sudo apt-get install pipewire libasound2-plugins libportaudio2 portaudio19-dev`
    - Stop and Disable Raspotify Service.
        - `sudo systemctl stop raspotify.service`
        - `sudo systemctl disable raspotify.service`
    - Create User Service.
        - `mkdir -p ~/.config/systemd/user/`
        - `mkdir -p ~/.cache/raspotify`
        - `cp service/raspotify.service ~/.config/systemd/user/raspotify.service`
        - `systemctl --user daemon-reload`
        - `systemctl --user enable raspotify.service`
        - `systemctl --user start raspotify.service`
    - Set Your Speaker.
        - `wpctl status`
        - Remember your Sinks ID
        - `DEFAULT_SINK_ID=<your id>`
        - `NODE_NAME=$(pw-cli info $DEFAULT_SINK_ID | grep 'node.name = ' | head -n 1 | cut -d '"' -f 2)`
        - `MONITOR_SOURCE_NAME="${NODE_NAME}.monitor"`
        - Check your monitor source name
            - `echo $MONITOR_SOURCE_NAME`
            - example: `alsa_output.usb-Apple_Computer__Inc._Speakers_p4000-00.analog-stereo.monitor`
    - Check for Playing and Recording at the Same Time for Testing.
        - Play spotify music on raspi using Spotify Connect
        - Record playing music
            - `PULSE_SOURCE=$MONITOR_SOURCE_NAME arecord -D pulse -r 48000 -f S16_LE -c 2 output.wav`
        
3. Install rpi-rgb-led-matrix
    - Refer to this guide to install the Python bindings: [python bindings](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python)
    - Build the python bindings:
        - `git clone https://github.com/hzeller/rpi-rgb-led-matrix.git`
        - `cd rpi-rgb-led-matrix/bindings/python/`
        - `sudo apt-get update && sudo apt-get install python3-dev cython3 -y`
        - `make build-python` 
    - Install `rpi-rgb-led-matrix` into your venv:
        - `cd /usr/local/bin/LED-Jukebox`
        - `python -m venv venv`
        - `source venv/bin/activate`
        - `cd rpi-rgb-led-matrix/bindings/python/`
        - `pip install .`
    - Set `dtparam=audio=off` in `/boot/firmware/config.txt` file.
    - Add snd_bcm2835 to blacklist
        ```bash
        cat <<EOF | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
        blacklist snd_bcm2835
        EOF

        sudo update-initramfs -u
        ```
    - Set `isolcpus=3` in the end of `/boot/firmware/cmdline.txt` file.
        - `sudo vim /boot/firmware/cmdline.txt`
            - example:`console=serial0,115200 console=tty1 root=PARTUUID=2b5c324a-02 rootfstype=ext4 fsck.repair=yes rootwait cfg80211.ieee80211_regdom=JP isolcpus=3`
    - Reboot your pi.
        - `sudo reboot`

4. Setup LED-Jukebox
    - Setup Services
        - Setup MQTT as a system service.
        - `sudo apt-get install mosquitto mosquitto-clients`
        - `sudo systemctl enable mosquitto.service`
        - `sudo systemctl start mosquitto.service`
        - Set MQTT broker service
            - `sudo cp service/led-jukebox-mqtt.service /etc/systemd/system/led-jukebox-mqtt.service`
            - `sudo systemctl daemon-reload`
            - `sudo systemctl enable led-jukebox-mqtt.service`
            - `sudo systemctl start led-jukebox-mqtt.service`
        - Set LED matrix subscriber
            - `sudo cp service/led-jukebox-led-matrix.service /etc/systemd/system/led-jukebox-led-matrix.service`
            - `sudo systemctl daemon-reload`
            - `sudo systemctl enable led-jukebox-led-matrix.service`
            - `sudo systemctl start led-jukebox-led-matrix.service`
        - Set Beats publisher as a user service.
            - `cp service/led-jukebox-beats.service ~/.config/systemd/user/led-jukebox-beats.service`
            - `systemctl --user daemon-reload`
            - `systemctl --user enable led-jukebox-beats.service`
            - `systemctl --user start led-jukebox-beats.service`
        - Auto login setting
            - `sudo vim  /etc/systemd/system/getty.target.wants/getty@tty1.service`
                ```
                #ExecStart=-/sbin/agetty -o '-p -- \\u' --noclear - $TERM
                ExecStart=-/sbin/agetty --autologin <your user name> --noclear %I $TERM
                ```
            - `sudo systemctl daemon-reload`
            - `sudo reboot`
    

- renderer settings
sudo apt-get install -y build-essential python3-dev libgles2-mesa-dev mesa-utils
sudo apt-get install -y libgles2-mesa-dev libegl1-mesa-dev libgbm-dev libdrm-dev mesa-utils
Xvfb (X virtual framebuffer) を使用する: これが最も一般的な方法です。Xvfb は、実際の画面出力なしに動作する Xサーバーです。

まず、Xvfb をインストールします (Raspberry Pi OS の場合):
sudo apt-get update
sudo apt-get install xvfb
次に、Xvfb をバックグラウンドで起動します。例えば、ディスプレイ番号 :1 を使用する場合:
Xvfb :1 -screen 0 1024x768x24 &
そして、Python スクリプトを実行する前に、DISPLAY 環境変数を設定します:
export DISPLAY=:1

あるいは、Python スクリプトの冒頭で DISPLAY 環境変数を設定することもできます。