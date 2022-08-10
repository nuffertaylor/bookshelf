function getCookie(cname) {
  let name = cname + "=";
  let decodedCookie = decodeURIComponent(document.cookie);
  let ca = decodedCookie.split(';');
  for(let i = 0; i <ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) == ' ') {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return null;
}

function setCookie(cname, cvalue) {
  const d = new Date();
  d.setTime(d.getTime() + (NUM_DAYS_STAY_LOGGEDIN * 24 * 60 * 60 * 1000));
  let expires = "expires="+d.toUTCString();
  document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getLocalIPAddress(callback)
{
  var oReq = new XMLHttpRequest();
  oReq.onreadystatechange = function(err){
    if (oReq.readyState == 4 && oReq.status == 200){
      let res = oReq.responseText.replace('?', '').replace('(','').replace(')','').replace(';','');
      callback(JSON.parse(res)["ip"]);
    }
  }
  oReq.open("GET", "https://api.ipify.org?format=jsonp&callback=?");
  oReq.send();
}

function validUrl(url){
  return /((([A-Za-z]{3,9}:(?:\/\/)?)(?:[-;:&=\+\$,\w]+@)?[A-Za-z0-9.-]+|(?:www.|[-;:&=\+\$,\w]+@)[A-Za-z0-9.-]+)((?:\/[\+~%\/.\w-_]*)?\??(?:[-\+=&;%@.\w_]*)#?(?:[\w]*))?)/.test(url);
}

function onlyDigits(str){
  return /^\d+$/.test(str);
}

function onlyNumbers(string) { 
  return (string.match(/^[0-9]+$/) != null); 
}

function getRequest(path, callback){
  let httpGet = new XMLHttpRequest();
  httpGet.onreadystatechange = callback;
  httpGet.open("GET", path, true);
  httpGet.send();
}

function disableElement(element){
  element.disabled = !element.disabled;
}