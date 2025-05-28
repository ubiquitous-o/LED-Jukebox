# LED Jukebox
This is the LED Jukebox, an audio-reactive system with five LED panels and four speakers.
![LED-Jukebox](image/sample.gif)

[sample video is here](https://www.instagram.com/reel/DKE6UU8N7yy/?utm_source=ig_web_copy_link&igsh=MzRlODBiNWFlZA==)

## Hardware Specifications
- Raspberry Pi 4B, 64GB microSD, Raspberry pi os lite(64-bit)
- [P2.5 64x64 RGB LED Matrix Panel](https://www.amazon.co.jp/dp/B07PK5J21V?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_2&th=1) x 5    
- [5V 40A Power Supply](https://www.amazon.co.jp/dp/B0B74KV3BB?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1&th=1) x1
- [8Ω 10W Speaker](https://akizukidenshi.com/catalog/g/g116600/) x4
- [10W+10W Stereo USB DAC Amplifier](https://akizukidenshi.com/catalog/g/g102404/) x1
- [Neodymium magnets(φ6mm x 3mm)](https://jp.daisonet.com/products/4549131156621) for attaching LED panels and top plate to the main body. x44
- [Ceiling outlet connector](https://www.amazon.co.jp/dp/B09XD5T959?ref=ppx_yo2ov_dt_b_fed_asin_title) for power supply. x1
- 3D printed parts. Print the models in the `3d_models` directory.
    - main_carrige.stl x1
        - The main body of the jukebox.
    - top_plate.stl x1
        - The top plate of the jukebox. Holds ceiling outlet connecter.
    - speaker_carriage.stl x1
        - The speaker carriage. Holds four speakers.
    - panel_adapter.stl x5
        - The LED panel carriage. Holds five LED panels. Attaches to the main body using magnets.

## Dependencies
- [Raspotify](https://github.com/dtcooper/raspotify): Streams Spotify music using an open-source client for Spotify Connect on Raspberry Pi.
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix): Used for controlling the LED panels.
- [MQTT](https://mqtt.org/): Used for communication between some components.
- [PyOpenGL](https://github.com/mcfletch/pyopengl): Used for rendering the visualizer.
- [LED-Jukebox-Visualizer](https://github.com/ubiquitous-o/LED-Jukebox-Visualizer/tree/f508b67ac83f24e6a895d195ace6519edb1c6f01): The rendering library for LED-Jukebox.

## Setup
1. Clone this repository.
    - `cd /usr/local/bin`
    - `git clone --recursive https://github.com/ubiquitous-o/LED-Jukebox.git`
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
    - Setup System Services
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
    

5. Renderer Settings
    - LED-Jukebox is rendered using OpenGL.
        - `sudo apt-get install -y build-essential python3-dev libgles2-mesa-dev mesa-utils libgbm-dev libdrm-dev xvfb`
    - Set gpu_memory in `/boot/firmware/config.txt` file.
        - `sudo vim /boot/firmware/config.txt`
            ```
            gpu_mem=128
            ```
    - Install[ `pyopengl` and `pyopengl-accelerate`](https://github.com/mcfletch/pyopengl).
        - Clone the repository.
            - `git clone https://github.com/mcfletch/pyopengl.git`
            - `cd /usr/local/bin/LED-Jukebox`
            - `source venv/bin/activate`
            - `cd pyopengl`
            - `pip install -e .`
            - `cd accelerate`
            - `pip install -e .`
    - Install python dependencies.
        - `pip install -r requirements.txt`
