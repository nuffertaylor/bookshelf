import got from 'got';

process.on('uncaughtException', function (err) {
  console.log(err);
}); 

function get_book_url_from_book_id(book_id){
  const URL_PREFIX = "https://www.goodreads.com/book/show/";
  return URL_PREFIX + book_id;
}

const find_json_in_str = (str) => {
  let found_json = [];
  let brace_stack = [];
  for(let i = 0; i < str.length; i++){
    if(str.charAt(i) === '{' && str.charAt(i+1) === '"') {
      //push the position of the brace
      brace_stack.push(i);
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
};

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
  const page = await got.get(book_url);

  // const { statusCode, page_HTML, headers } = await curly.get(book_url);
  const json_list = find_json_in_str(page.body);
  const second_run = find_json_in_str(json_list[0])[0];
  if(!second_run) return;
  const parsed_json = JSON.parse(second_run);
  return {
    statusCode: page.statusCode,
    body: {
      book_id : book_id,
      title : parsed_json.name.replace(/&apos;/g, "'"),
      isbn: parsed_json.isbn,
      author : parsed_json.author[0].name,
      num_pages : parsed_json.numberOfPages,
    }
  };
};

export default main;