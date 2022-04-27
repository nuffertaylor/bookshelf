var currentState = "login";
const REGISTER_ALT_TEXT = "Don't have an account? Click here to register.";
const LOGIN_ALT_TEXT = "Already have an account? Click here to login.";
const NUM_DAYS_STAY_LOGGEDIN = 7;

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
  getLocalIPAddress(
    (ip) => {
      var data = {
        requestType : currentState,
        username : username,
        password : password,
        email : email,
        ip: ip
      };
      sendRequestToServer(data);
  });
}

function handleResponse(res)
{
  console.log(res);
  res = JSON.parse(res);
  console.log(res);
  if(res.statusCode == 200)
  {
    alert("Successfully logged in");
    setCookie("username", res.body.username);
    setCookie("authtoken", res.body.authtoken);
  }
  else
  {
    alert(res.body);
  }
}

async function sendRequestToServer(data)
{
  var httpPost = new XMLHttpRequest(),
      path = "https://vi64h2xk34.execute-api.us-east-1.amazonaws.com/alpha/loginregister",
      data = JSON.stringify(data);
  httpPost.onreadystatechange = (err) =>
  {
    if (httpPost.readyState == 4) handleResponse(httpPost.responseText);
  };
  // Set the content type of the request to json since that's what's being sent
  httpPost.open("POST", path, true);
  httpPost.setRequestHeader('Content-Type', 'application/json');
  httpPost.send(data);
};

function runget()
{
  var oReq = new XMLHttpRequest();
  oReq.onreadystatechange = (err) =>
  {
    if (oReq.readyState == 4 && oReq.status == 200){
      let res = oReq.responseText;
      console.log(res);
    }
  }
  oReq.open("GET", "https://msrjars0ja.execute-api.us-east-1.amazonaws.com/alpha/spine?title=Silence&book_id=25663542");
  oReq.send();
}