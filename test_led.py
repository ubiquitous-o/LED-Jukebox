#!/usr/bin/env python
import time
import sys
import requests

from modules import config
# from modules import spotify
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image

if len(sys.argv) < 2:
    sys.exit("Require an image argument")
else:
    image_file = sys.argv[1]

img = Image.open(image_file)
# track_id = "11vZhGXiQJg1ABYOSeKqB4"


# Configuration for the matrix
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 5
options.gpio_slowdown = 5
# options.parallel = 1
options.hardware_mapping = 'regular'  # If you have an Adafruit HAT: 'adafruit-hat'
matrix = RGBMatrix(options = options)

# image_url = spotify.get_album_url(track_id)
# print(track_id)
# img = Image.open(requests.get(image_url, stream=True).raw)
if img.size[0] != 64 or img.size[1] != 64:
    img = img.resize((64, 64), resample=Image.BICUBIC)

# Concatenate the image horizontally 5 times
concatenated_img = Image.new('RGB', (img.width * 5, img.height))
for i in range(5):
    concatenated_img.paste(img, (i * img.width, 0))

# Make image fit our screen.
# concatenated_img.thumbnail((matrix.width, matrix.height), Image.ANTIALIAS)
matrix.SetImage(concatenated_img)
while True:
    time.sleep(100)
