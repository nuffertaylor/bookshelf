const corsURL = "https://cors-anywhere.herokuapp.com/"; //CHANGE TO YOUR PERSONAL CORS-ANYWHERE URL
function get_gr_data(path) {
  let httpGet = new XMLHttpRequest();
  httpGet.onreadystatechange = () => {
    if (httpGet.readyState == 4) {
      // console.log(httpGet.responseText);
      let htmlObject = document.createElement("div");
      htmlObject.innerHTML = httpGet.responseText;
      document.getElementById("bs_gr_holder").appendChild(htmlObject);
      let l = document.links;
      for (var i = 0; i < l.length; i++) {
        if (l[i].href.includes("/review/list/")) {
          let res = fetch_book_data(l[i].href, book_id);
          if(res) return res; //return book data if we found the book we're looking for in the list we searched
        }
      }
      return ("found no relevant links");
    }
  };
  httpGet.open("GET", path, true);
  httpGet.send();
}

const REQUEST_DOMAIN = "nuffertaylor.github.io";

function fetch_book_data(list_url, book_id) {
  let url = list_url.replace("list", "list_rss");
  url = url.replace(REQUEST_DOMAIN, "www.goodreads.com");
  // url = corsURL + url;
  feednami.load(url, (result)=>{
		if(result.error) {
			console.log(result.error);
		} else {
			var entries = result.feed.entries;
			for(var i = 0; i < entries.length; i++){
				var entry = entries[i];
        if(entry["rss:book_id"]["#"] == book_id.toString()){
          fill_input_fields(entry);
          clear_gr_element();
          return;
        }
			}
      return false;
		}
	});
}

function fill_input_fields(entry){
  title.value = entry["title"];
  book_id.value = entry["rss:book_id"]["#"];
  pubDate.value = entry["rss:book_published"]["#"];
  authorName.value = ["rss:author_name"]["#"];
  disableElement(title);
  disableElement(book_id);
  disableElement(pubDate);
  disableElement(authorName);
}

function clear_gr_element(){
  document.getElementById("bs_gr_holder").innerHTML = "";
}

function fetch_goodreads_data(){
  let origin = document.getElementById("gr_fetch_data").value;
  let path = corsURL;
  if(onlyNumbers(origin)) {
    path = path + 
    "https://www.goodreads.com/book/show/" +
    origin.toString();
  }
  else if(validUrl(origin)) {
    path = path + origin;
  }
  else {
    alert("invalid goodreads url/book_id provided");
    return;
  }

  get_gr_data(path);
}