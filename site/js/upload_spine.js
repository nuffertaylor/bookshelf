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
  imageForm.addEventListener("submit", async event => {
    event.preventDefault();

    if(!onlyNumbers(book_id.value)) {
      alert("invalid goodreads book id!");
      book_id.focus();
      return;
    }
    if(!validDimensions(dimensions.value)) {
      alert("invalid dimension input, should be in format 1 x 2 x 3");
      dimensions.focus();
      return;
    }

    if(!loggedIn()){
      alert("must be logged in to submit new spine");
      return;
    }

    var data = {
      title : title.value,
      book_id : book_id.value,
      dimensions : dimensions.value,
      pubDate : pubDate.value,
      authorName : authorName.value,
      genre : genre.value,
      image : b64Image,
      username : getCookie("username"),
      authtoken : getCookie("authtoken")
    };
    sendRequestToServer(data, (value)=>{
        if(value) 
        {
          alert("Successfully uploaded " + title.value);
          //clear form
          title.value = "";
          book_id.value = "";
          dimensions.value = "";
          pubDate.value = "";
          authorName.value = "";
          genre.value = "";
          imageInput.value = "";
          document.getElementById('displayImage').src = "";
        }
        else alert("Something went wrong uploading " + title.value);
    });
  });
};

function onlyNumbers(string) { return (string.match(/^[0-9]+$/) != null); }

function validDimensions(string) { return (string.match(/^([0-9]+\.*[0-9]* *[xX] *){2}([0-9]+\.*[0-9]*)/) != null); }

function loggedIn(){
  let u = getCookie("username");
  let a = getCookie("authtoken");
  if(u == null || a == null) return false;
  return true;
}

function encodeImageFileAsURL(element) {
  var file = element.files[0];
  document.getElementById('displayImage').src = window.URL.createObjectURL(file);
  var reader = new FileReader();
  reader.onloadend = function() {
    b64Image = reader.result;
  }
  reader.readAsDataURL(file);
}

function sendRequestToServer(data, callback){
  var httpPost = new XMLHttpRequest();
  var path = "https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/spine";
  var data = JSON.stringify(data);
  httpPost.onreadystatechange = function(err) {
          if (httpPost.readyState == 4){
            if (httpPost.status == 200) callback(true);
            else callback(false);
          }
      };
  // Set the content type of the request to json since that's what's being sent
  httpPost.open("POST", path, true);
  httpPost.setRequestHeader('Content-Type', 'application/json');
  httpPost.send(data);
};