import scrape from 'website-scraper'; // only as ESM, no CommonJS
import { parse as parse_html} from 'node-html-parser';
import * as fs from 'node:fs';

process.on('uncaughtException', function (err) {
  console.log(err);
}); 

function get_book_url_from_book_id(book_id){
  const URL_PREFIX = "https://www.goodreads.com/book/show/";
  return URL_PREFIX + book_id;
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

  if(!book_id) return { statusCode: 500 };
  
  //It's currently broken, so just always return 500 and the book_id we got.
  return { statusCode: 500, body: { book_id: book_id} };
  
  
  const book_url = get_book_url_from_book_id(book_id);

  const dir_to_scrape_to = '/tmp/x';
  const options = {
    urls: [book_url],
    directory: dir_to_scrape_to
  };

  //sometimes a request might not actually pull any data. We need (at least) the title and the author. If we can't find that data, try again.
  //We'll try five times, and at that point throw an error
  let parsed = null;
  for(let i = 0; i < 5; i++){
    console.log("starting scrape");
    const scraped = await scrape(options);
    const html = scraped[0].text;
    const page = parse_html(html);
    const jsonScriptElement = page.querySelector("script[type='application/ld+json']");
    if(jsonScriptElement) { 
      const json = jsonScriptElement.innerHTML;
      parsed = JSON.parse(json);
      i=6;
    }
    //delete directory we scraped to
    fs.rmSync(dir_to_scrape_to, { recursive: true, force: true });
  }

  if(!parsed) return { statusCode: 500 };
  return {
    statusCode: 200,
    body: {
      book_id: book_id,
      title: parsed.name,
      num_pages: parsed.numberOfPages,
      author: parsed.author[0].name
    }
  }
};

export default main;