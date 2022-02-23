var imageForm;
var imageInput;
var title;
var book_id;
var pubDate;
var authorName;
var genre;
var b64Image = null;
window.onload = ()=> {
  imageForm = document.getElementById("imageForm");
  imageInput = document.getElementById("imageInput");
  title = document.getElementById("title");
  book_id = document.getElementById("book_id");
  dimensions = document.getElementById("dimensions");
  pubDate = document.getElementById("pubDate");
  authorName = document.getElementById("authorName");
  genre = document.getElementById("genre");
  console.log('gjh');
  imageForm.addEventListener("submit", async event => {
    event.preventDefault();

    var data = {
      title : title.value,
      book_id : book_id.value,
      dimensions : dimensions.value,
      pubDate : pubDate.value,
      authorName : authorName.value,
      genre : genre.value,
      image : b64Image
    };
    console.log(JSON.stringify(data));
  });
};

function onlyNumbers(string) { return (string.match(/^[0-9]+$/) != null); }

function encodeImageFileAsURL(element) {
  var file = element.files[0];
  document.getElementById('displayImage').src = window.URL.createObjectURL(file);
  var reader = new FileReader();
  reader.onloadend = function() {
    b64Image = reader.result;
  }
  reader.readAsDataURL(file);
}

var sendRequestToServer = function(name, data){
  var httpPost = new XMLHttpRequest(),
      path = "http://127.0.0.1:8000/uploadImage/" + name,
      data = JSON.stringify(data);
  httpPost.onreadystatechange = function(err) {
          if (httpPost.readyState == 4 && httpPost.status == 200){
              console.log(httpPost.responseText);
          } else {
              console.log(err);
          }
      };
  // Set the content type of the request to json since that's what's being sent
  httpPost.setHeader('Content-Type', 'application/json');
  httpPost.open("POST", path, true);
  httpPost.send(data);
};