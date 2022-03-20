var currentState = "login";
const REGISTER_ALT_TEXT = "Don't have an account? Click here to register.";
const LOGIN_ALT_TEXT = "Already have an account? Click here to login.";

function alternateLoginRegister()
{
  if(currentState == "login")
  {
    currentState = "register";
    document.getElementById("email").style.display = "";
    document.getElementById("submitCredentials").innerHTML = "Register";
    document.getElementById("clickToAlternate").innerHTML = LOGIN_ALT_TEXT;
  }
  else if(currentState == "register")
  {
    currentState = "login";
    document.getElementById("email").style.display = "none";
    document.getElementById("submitCredentials").innerHTML = "Login";
    document.getElementById("clickToAlternate").innerHTML = REGISTER_ALT_TEXT;
  }
}

function submitLoginRegister()
{
  let username = document.getElementById("username").value;
  let password = document.getElementById("password").value;
  let email = document.getElementById("email").value;
  getLocalIPAddress().then(
    (ip) => {
      var data = {
        requestType : currentState,
        username : username,
        password : password,
        email : email,
        ip: ip
      };
      sendRequestToServer(data).then(
        (res) => {
          if(res)
          {
            console.log(res);
          }
          else{
            //identify what went wrong and tell the user
          }
        },
        (err) => {console.log(err)}
      );
    },
    (err) => (console.log(err))
  );
}

async function sendRequestToServer(data){
  var httpPost = new XMLHttpRequest(),
      path = "https://msrjars0ja.execute-api.us-east-1.amazonaws.com/alpha/loginregister",
      data = JSON.stringify(data);
  httpPost.onreadystatechange = function(err) {
          if (httpPost.readyState == 4 && httpPost.status == 200)
              return httpPost.responseText;
  };
  // Set the content type of the request to json since that's what's being sent
  httpPost.open("POST", path, true);
  httpPost.setRequestHeader('Content-Type', 'application/json');
  httpPost.send(data);
};

async function getLocalIPAddress()
{
  var oReq = new XMLHttpRequest();
  oReq.onreadystatechange = function(err){
    if (oReq.readyState == 4 && oReq.status == 200){
      let res = oReq.responseText.replace('?', '').replace('(','').replace(')','').replace(';','');
      return (JSON.parse(res)["ip"]);
    }
  }
  oReq.open("GET", "https://api.ipify.org?format=jsonp&callback=?");
  oReq.send();
}