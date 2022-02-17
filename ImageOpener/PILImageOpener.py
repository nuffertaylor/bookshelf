from PIL import Image

class PILImageOpener:
  def open(fileName) -> Image:
    return Image.open(fileName)