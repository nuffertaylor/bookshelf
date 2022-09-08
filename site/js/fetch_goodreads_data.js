const CORS_URL = "https://serveless-cors-bs.vercel.app/api/cors?url="; //CHANGE TO YOUR PERSONAL CORS-ANYWHERE URL
const REQUEST_DOMAIN = "nuffertaylor.github.io";

const fetch_book_data_recursive = function(review_links, book_id){
  console.log("in recursive fetchbooks");
  console.log("review_links is " + review_links.length.toString() + " items long");
  if(review_links.length < 1){
    alert("GoodReads data pull failed; Please enter book information manually.");
    clear_gr_element();
  }
  let list_url = review_links.shift(); //this grabs link[0] and pops it from the array
  let url = list_url.replace("list", "list_rss");
  url = url.replace(REQUEST_DOMAIN, "www.goodreads.com");
  // url = CORS_URL + url;
  //use feednami to parse rss data from url
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
          return true;
        }
			}
		}
    //if we get this far, we havent found the data we're looking for yet. try the next link in the list.
    fetch_book_data_recursive(review_links, book_id);
    return false;
	});
}

function get_gr_data(path) {
  let book_id = path.replace(/\D/g,'');
  let httpGet = new XMLHttpRequest();
  httpGet.onreadystatechange = () => {
    if (httpGet.readyState == 4) {
      let htmlObject = document.createElement("div");
      htmlObject.innerHTML = httpGet.responseText;
      document.getElementById("bs_gr_holder").appendChild(htmlObject);
      let l = document.links;
      let review_links = [];
      for (var i = 0; i < l.length; i++) {
        if (l[i].href.includes("/review/list/")) {
          review_links.push(l[i].href);
        }
      }
      console.log("review_links is " + review_links.length.toString() + " items long before starting recurse");
      fetch_book_data_recursive(review_links, book_id);
    }
  };
  httpGet.open("GET", path, true);
  httpGet.send();
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
  let path = CORS_URL;
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
  console.log(path);

  get_gr_data(path);
}