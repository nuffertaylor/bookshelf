import fetch from 'node-fetch';
import { parse as parse_html} from 'node-html-parser';

process.on('uncaughtException', function (err) {
  console.log(err);
}); 

// exports.handler = async (event) => {
//   const response = {
//     statusCode: 200,
//     body: JSON.stringify(main(event.url)),
//   };
//   return response;
// };

function get_book_url_from_book_id(book_id){
  const URL_PREFIX = "https://www.goodreads.com/book/show/";
  return URL_PREFIX + book_id;
}

async function fetch_page(url){
  const response = await fetch(url);
  const body = await response.text();
  return body;
}

function remove_non_numeric_char_from_str(str){return str.replace(/\D/g,'');}

function get_book_data_from_book_page(page, book_id){
  const book_title = page.querySelector("#bookTitle").childNodes[0]._rawText.trim();
  let book_series = page.querySelector("#bookSeries");
  // check if book is in series
  if(book_series.querySelector("a")) book_series = " " + book_series.querySelector("a").childNodes[0]._rawText.trim();
  else book_series = "";
  const gr_title = book_title + book_series;
  const author_name = page.querySelector(".authorName").querySelector('[itemprop="name"]').childNodes[0]._rawText.trim();
  const num_pages = removeNonNumericCharFromStr(page.querySelector('[itemprop="numberOfPages"]').childNodes[0]._rawText.trim());
  const pub_date_string = page.querySelector('#details').querySelectorAll(".row")[1].childNodes[0]._rawText.trim().split("\n")[1].trim();
  const genre = page.querySelector(".bookPageGenreLink").childNodes[0]._rawText.trim();
  console.log(genre);
  return {
    book_id : book_id,
    title : gr_title,
    author : author_name,
    pubDate : pub_date_string,
    num_pages : num_pages,
    genre : genre
  };
}

async function main(url){
  const book_id = remove_non_numeric_char_from_str(url);
  const book_url = get_book_url_from_book_id(book_id);
  const page_HTML = await fetch_page(book_url);
  const page = parse_html(page_HTML);
  const book = get_book_data_from_book_page(page, book_id);
  console.table(book);
}
