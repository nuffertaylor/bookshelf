window.onload = ()=>{
  document.getElementById("submit").onclick = (e)=>{
    let userid = document.getElementById("userid").value;
    if(!userid) {
      alert("please provide goodreads userid!");
      document.getElementById("userid").focus();
      return;
    }
    let shelfname = document.getElementById("shelfname").value;
    if(!shelfname) {
      alert("you have to provide a shelfname!");
      document.getElementById("shelfname").focus();
      return;
    }
    if(userid && shelfname){
      getGRShelf(userid, shelfname);
    }
  };
};

function getGRShelf(userid, shelfname) {
  let querystr = "userid=" + userid + "&shelfname=" + shelfname;
  sendGetRequestToServer("getgrbookshelf", querystr, (res)=>{
    let resObj = JSON.parse(res);
    var found = resObj["body"]["found"];
    var unfound = resObj["body"]["unfound"];
    document.getElementById("numFound").innerHTML = "Found " + (found.length).toString() + " of " + (found.length + unfound.length).toString() + " book spines.";
    if(unfound.length > 0) {
      document.getElementById("numUnfound").innerHTML = (unfound.length).toString() + " spines not in the database.";
      document.getElementById("fakeSpines").classList.remove("hide");
      document.getElementById("fakeSpinesLabel").classList.remove("hide");
    }
    document.getElementById("form_a").classList.add("hide");
    document.getElementById("form_b").classList.remove("hide");
    document.getElementById("submitGen").onclick = ()=>{
      let booklist = found;
      if(document.getElementById("fakeSpines").checked) {
        booklist.push(...unfound);
      }
      var data = {
        bookList : booklist
      }
      document.getElementById("form_b").classList.add("hide");
      document.getElementById("temp_img").classList.remove("hide");
      sendPostRequestToServer("genshelf", data, (res)=>{
        let resObj = JSON.parse(res);
        let url = resObj["body"];
        document.getElementById("temp_img").src = url;
      });
    }
  });
}

async function sendGetRequestToServer(method, querystr, callback){
  var xhttp = new XMLHttpRequest();
  var path = "https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/" + method + "?" + querystr;
  xhttp.onreadystatechange = function() {
      if (this.readyState == 4 && this.status == 200) {
        callback(xhttp.responseText);
      } //TODO handle other status codes
  };
  xhttp.open("GET", path, true);
  xhttp.send();

}

async function sendPostRequestToServer(method, data, callback) {
  var httpPost = new XMLHttpRequest();
  var path = "https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/" + method;
  var data = JSON.stringify(data);
  httpPost.onreadystatechange = (err) =>{
    if(httpPost.readyState == 4) callback(httpPost.responseText);
  };
  // Set the content type of the request to json since that's what's being sent
  httpPost.open("POST", path, true);
  httpPost.setRequestHeader('Content-Type', 'application/json');
  httpPost.send(data);
};