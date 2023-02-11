import got from 'got';
import { parse as parse_html} from 'node-html-parser';
import { Curl } from "node-libcurl";

process.on('uncaughtException', function (err) {
  console.log(err);
}); 

function get_book_url_from_book_id(book_id){
  const URL_PREFIX = "https://www.goodreads.com/book/show/";
  return URL_PREFIX + book_id;
}

async function fetch_page(url){
  const response = await got.get(url);
  const body = response.rawBody;
  return body;
}

//goodreads has changed their site, so this function is now deprecated.
function get_book_data_from_book_page(page, book_id){
  let book_title = "";
  const book_title_el = page.querySelector("#bookTitle");
  if(book_title_el && book_title_el.childNodes)
    book_title = book_title_el.childNodes[0]._rawText.trim();
  
  let book_series = page.querySelector("#bookSeries");
  // check if book is in series
  if(book_series.querySelector("a")) {
    book_series = " " + book_series.querySelector("a").childNodes[0]._rawText.trim();
    //add a comma between the number and the series number
    const temp = book_series.split('#');
    if(temp.length > 1) book_series = temp[0].trim() + ", #" + temp[1];
    else book_series = temp[0].trim();
  }
  else book_series = "";
  const gr_title = book_title + " " + book_series;

  //TODO: Handling for multiple authors (currently will only grab one)
  let author_name = "";
  const author_name_el = page.querySelector(".authorName");
  if(author_name_el) {
    const name_prop = author_name_el.querySelector('[itemprop="name"]');
    if(name_prop && name_prop.childNodes) author_name = name_prop.childNodes[0]._rawText.trim();
  }
  
  let num_pages = "";
  const num_pages_el = page.querySelector('[itemprop="numberOfPages"]');
  if(num_pages_el && num_pages_el.childNodes) {
    num_pages = remove_non_numeric_char_from_str(page.querySelector('[itemprop="numberOfPages"]').childNodes[0]._rawText.trim());
  }

  //TODO: This successfully gets the publication date of the provided edition. But more useful to the user is the original publication date.
  let pub_date_string = ""
  const details_element = page.querySelector('#details');
  if(details_element) {
    const rows = details_element.querySelectorAll(".row");
    if(rows && rows.length > 1)
      if(rows[1] && rows[1].childNodes) 
        pub_date_string = rows[1].childNodes[0]._rawText.trim().split("\n")[1].trim();
  }
  let genre = "";
  const genre_el = page.querySelector(".bookPageGenreLink");
  if(genre_el && genre_el.childNodes)
    genre = genre_el.childNodes[0]._rawText.trim();
  return {
    book_id : book_id,
    title : gr_title,
    author : author_name,
    pubDate : pub_date_string,
    num_pages : num_pages,
    genre : genre
  };
}

const get_book_data_from_page = (page) => {
  // console.log(page.title);
  console.log(page.querySelector('title').innerHTML);

}

const get_last_sub_dir_from_url = (url) => {
  let res = url.split('/').at(-1);
  if(res === '') res = url.split('/').at(-2);
  if(typeof res === "string") return res;
  return "";
};
const remove_query_string = (url) => { return url.split('?')[0]; };
const remove_text_title = (url) => { return url.split(/-|\./)[0]; };
const remove_non_numeric_char_from_str = (str) => { return str.replace(/\D/g,''); };

const main = async function (url){
  if(!url || typeof url !== "string") return {};
  url = get_last_sub_dir_from_url(url);
  url = remove_query_string(url);
  url = remove_text_title(url);
  const book_id = remove_non_numeric_char_from_str(url);
  if(!book_id) return {};
  const book_url = get_book_url_from_book_id(book_id);

  const find_json_in_str = (str) => {
    let found_json = [];
    let brace_stack = [];
    for(let i = 0; i < str.length; i++){
      if(str.charAt(i) === '{' && str.charAt(i+1) === '"') {
        //push the position of the brace
        brace_stack.push(i)
      }
      else if(str.charAt(i) === '}') {
        if(brace_stack.length > 0){
          let prev_pos = brace_stack.pop();
          if(brace_stack.length === 0) {
            //we have a complete json element! let's store it
            found_json.push(str.substr(prev_pos, i+1));
          }
        }
        //if the length of brace_stack IS 0, there's a brace mismatch. but for now we'll just ignore that 
      }
    }
    return found_json;
  }

  const parse_list_of_json = (json_list) => {
    let parsed_json = []
    for(const j of json_list){
      parsed_json.push(JSON.parse(j));
    }
    return parsed_json;
  }


  const curlTest = new Curl();

  curlTest.setOpt(Curl.option.URL, book_url);
  const terminate = curlTest.close.bind(curlTest);

  curlTest.on("end", function (statusCode, data, headers) {
    const json_list = find_json_in_str(data);
    // const parsed_json = parse_list_of_json(json_list)
    console.log(json_list[0]);
    // for(let i = 0 ; i < 20; i++) console.log(firstPart[i])
    // console.info("Status code " + statusCode);
    // console.info("***");
    // console.info("Our response: " + data);
    // console.info("***");
    // console.info("Length: " + data.length);
    // console.info("***");
    // console.info("Total time taken: " + this.getInfo("TOTAL_TIME"));
    // const page = parse_html(data);
    // const book = get_book_data_from_page(page);

    this.close();
  });
  curlTest.on("error", terminate);

  curlTest.perform();


  
  // const page_HTML = await fetch_page(book_url);
  
  // const book = get_book_data_from_page(page);
  // return book;
};

export default main;