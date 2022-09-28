from s3_dao import openS3Image
from PIL import Image

class S3ImageOpener:
  def open(filename) -> Image:
    return openS3Image(filename)