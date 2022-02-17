from PIL import Image

class ImageOpenerInterface:
  def open(fileName) -> Image:
    """Open the file and return a Pillow Image"""
    pass
  