import sys
from PIL import Image
import config
import spotify
import requests

track_ID = sys.argv[1]
event = sys.argv[2]

print("Event: " + event + "-called")

if event == "playing":
    image_url = spotify.get_album_url(track_ID)

    img = Image.open(requests.get(image_url, stream=True).raw)
    if img.size[0] != 64 or img.size[1] != 64:
        img = img.resize((64, 64), resample=Image.BICUBIC)
    print(img)
    img.save("/tmp/album_cover.jpg")
    print("save image to /tmp/hogehoge/tmp/album_cover.jpg")
    # pixoo.draw_image(img, image_resample_mode=ImageResampleMode.SMOOTH)
    # pixoo.push()
    # print("draw album cover")

elif event == "stopped" or event == "paused":
    # pixoo.draw_filled_rectangle((0, 0), (63, 63), rgb=(0, 0, 0))
    # pixoo.push()
    print("draw blackscreen")