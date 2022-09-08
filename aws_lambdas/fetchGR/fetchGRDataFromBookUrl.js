import fetch from 'node-fetch';
import { parse as parse_html} from 'node-html-parser';
import Parser from 'rss-parser';
const rss_parser = new Parser();


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
  return review_links;
}


async function fetch_book_data_recursive(review_links, book_id){
  if(review_links.length < 1){
    console.log("GoodReads data pull failed; Please enter book information manually.");
    return false;
  }
  let list_url = review_links.shift(); //this grabs link[0] and pops it from the array
  let url = "https://www.goodreads.com" + list_url.replace("list", "list_rss");
  console.log(url);

  let feed = await rss_parser.parseURL(url);
  feed.items.forEach(item => {
    const parse_item_content = (content) => {
      const split1 = content.split("<br/>");
      const split2 = split1.map(e => e.split(":"));
      let resultObj = {};
      split2.forEach(item => {if(item.length > 1) resultObj[item[0].trim()] = item[1].trim()});
      return resultObj;
    }
    //parse out the book_id for the given book (should be in an a tag in content)
    //compare found book_id to provided book_id. if a match, return the book data. else, continue recursing this function with now shorter list.
    //only do this parse if item.content exists!
    let book = parse_item_content(item.content);
    console.log(book);
    book.pubDate = item.pubDate; //needs to be parsed into just year, currently formatted like Sat, 11 Jun 2022 05:56:40 -0700
    book.title = item.title;
    console.log(item);
  })
}

const page_HTML = await fetchPageFromURL("https://www.goodreads.com/book/show/6444191-the-virgin-warrior");
const page = parse_html(page_HTML);
const review_links = getReviewLinksFromPage(page);
fetch_book_data_recursive(review_links);


