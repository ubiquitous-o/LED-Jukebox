# LED-Jukebox

## Hardware Specifications
- Raspberry Pi 4B
- [P2.5 64x64 RGB LED Matrix Panel](https://www.amazon.co.jp/dp/B07PK5J21V?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_2&th=1) x 5    
- [5V 40A Power Supply](https://www.amazon.co.jp/dp/B0B74KV3BB?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_1&th=1)
- [8Ω 10W Speaker](https://akizukidenshi.com/catalog/g/g116600/) x4
- [10W+10W Stereo USB DAC Amplifier](https://akizukidenshi.com/catalog/g/g102404/)
- USB microphone

## Dependencies
- [Raspotify](https://github.com/dtcooper/raspotify?tab=readme-ov-file): Streams Spotify music using an open-source client for Spotify Connect on Raspberry Pi.
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix): Used for controlling the LED panels.

## Setup
1. Install Raspotify
    - Set `handler.sh` as a Librespot Event Script
    - https://github.com/dtcooper/raspotify/wiki/How-To:-Listen-To-Librespot-Events
2. Install rpi-rgb-led-matrix ([python bindings](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python))


