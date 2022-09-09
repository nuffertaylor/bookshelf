import fetch from 'node-fetch';
import { parse as parse_html} from 'node-html-parser';
import Parser from 'rss-parser';
const rss_parser = new Parser({
  customFields: {
    item : [
      "author_name",
      "average_rating",
      "book_id",
      "book_published",
      "isbn",
      "title",
      "book"
    ]
  }
});


process.on('uncaughtException', function (err) {
  console.log(err);
}); 

// exports.handler = async (event) => {
//   const response = {
//     statusCode: 200,
//     body: JSON.stringify('Hello from Lambda!'),
//   };
//   return response;
// };

function getBookUrlFromBookId(book_id){
  const URL_PREFIX = "https://www.goodreads.com/book/show/";
  return URL_PREFIX + book_id;
}

async function fetchPageFromURL(url){
  const response = await fetch(url);
  const body = await response.text();
  return body;
}

function getAttrListFromRawAttrs(rawAttrs){
  const regex = /"[^"]+"|[^\s]+/g;
  /* Use 'map' and 'replace' to discard the surrounding quotation marks. */
  const result = rawAttrs.match(regex).map(e => e.replace(/"(.+)"/, "$1"));
  //there's some sketchiness with this regex i pulled off stack overflow. it doesn't seem to be splitting things like class="class1 class2" correctly. i should fix it. but will i?
  let mappedResult = {};
  result.forEach(e=>{
    const split_element = e.split('=');
    mappedResult[split_element[0]] = split_element[1];
  });
  return mappedResult;
}

function getReviewLinksFromPage(page){
  let l = page.getElementsByTagName("a");
  let review_links = [];
  for (var i = 0; i < l.length; i++) {
    const attrMap = (getAttrListFromRawAttrs(l[i].rawAttrs))
    if(typeof attrMap["href"] === "undefined") continue;
    if(attrMap["href"].includes("/review/list/")) 
      review_links.push(attrMap["href"]);
  }
  //convert review_links to set to remove duplicates and convert back to arr
  let unique_links = [...new Set(review_links)];
  return unique_links;
}


async function fetch_book_data_recursive(review_links, book_id){
  if(review_links.length < 1){
    console.log("GoodReads data pull failed; Please enter book information manually.");
    return false;
  }
  let list_url = review_links.shift(); //this grabs link[0] and pops it from the array
  let url = "https://www.goodreads.com" + list_url.replace("list", "list_rss");
  console.log("==========================================");
  console.log("starting parse for url " + url);
  console.log("there are " + review_links.length + " link remaining");
  console.log("==========================================");

  let feed = await rss_parser.parseURL(url);
  feed.items.forEach(item => {
    console.log("found book " + item.title + " with book_id " + item.book_id + "\tlooking for " + book_id);
    if(parseInt(item.book_id) != parseInt(book_id)) return;
    item.num_pages = item.book.num_pages;
    delete item.book;
    delete item.content;
    delete item.contentSnippet;
    return item;
  });
  return fetch_book_data_recursive(review_links, book_id);
}

function removeNonNumericCharFromStr(str){return str.replace(/\D/g,'');}

async function main(url){
  const book_id = removeNonNumericCharFromStr(url);
  const book_url = getBookUrlFromBookId(book_id);
  const page_HTML = await fetchPageFromURL(book_url);
  const page = parse_html(page_HTML);
  const review_links = getReviewLinksFromPage(page);
  console.log(review_links);
  const book = await fetch_book_data_recursive(review_links, book_id);
  console.log(book);
}

// main("https://www.goodreads.com/book/show/30558257-unsouled")