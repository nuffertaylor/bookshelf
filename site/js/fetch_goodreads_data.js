const corsURL = "https://cors-anywhere.herokuapp.com/"; //CHANGE TO YOUR PERSONAL CORS-ANYWHERE URL
function get_gr_data(path) {
  let book_id = path.replace(/^\D+/g, '');
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
          fetch_book_data(l[i].href, book_id);
          return; //we (should've) just found a link to a list with our desired book in it, so return so we only do this once.
        }
      }
      alert("GoodReads data pull failed; Please enter book information manually.");
      clear_gr_element();
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
  feednami.load(url).then(result => {
		if(result.error) {
			console.log(result.error);
		} else {
			let entries = result.entries;
			for(let i = 0; i < entries.length; i++){
				let entry = entries[i];
        if(entry["rss:book_id"]["#"] == book_id.toString()){
          let mappedData = {
            title : entry["title"],
            book_id : entry["rss:book_id"]["#"],
            pubDate : entry["rss:book_published"]["#"],
            authorName : entry["rss:author_name"]["#"]
          }
          fill_input_fields(mappedData);
          clear_gr_element();
          return;
        }
			}
      return false;
		}
	});
}

function fill_input_fields(entry){
  title.value = entry.title;
  book_id.value = entry.book_id;
  pubDate.value = entry.pubDate;
  authorName.value = entry.authorName;
  title.disabled = true;
  book_id.disabled = true;
  pubDate.disabled = true;
  authorName.disabled = true;
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