bg_url = "https://bookshelf-spines.s3.amazonaws.com/bookshelf1.jpg"

let result_canvas = document.createElement("canvas");
let canvas = document.createElement("canvas");



function convertCanvasToImage(canvas)
{
  let image = new Image();
  image.src = canvas.toDataURL();
  return image;
}