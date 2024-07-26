import puppeteer from 'puppeteer-core';
import chromium from 'chrome-aws-lambda';

const get_book_data_by_goodreads_id = async (goodreads_id) => {
  // Launch the browser and open a new blank page
  const browser = await puppeteer.launch({
    args: chromium.args,
    defaultViewport: chromium.defaultViewport,
    executablePath: await chromium.executablePath,
    headless: true
  });
  const page = await browser.newPage();

  const GOODREADS_PRE = 'https://www.goodreads.com/book/show/';

  // Navigate the page to a URL.
  await page.goto(GOODREADS_PRE + goodreads_id);

  const bookTitleElement = await page.$('[data-testid="bookTitle"]');
  const title = await bookTitleElement.evaluate(el => el.textContent);

  let series = null;
  // wrap in try catch. If there's an error here, there is no relevant series so just ignore
  try {
    const seriesElement = await page.$('[class="Text Text__title3 Text__italic Text__regular Text__subdued"]');
    series = await seriesElement.evaluate(el => el.firstChild.textContent);
  } catch {}

  const authorElement = await page.$('[data-testid="name"]');
  const author = await authorElement.evaluate(el => el.textContent);

  const publicationDateElement = await page.$('[data-testid="publicationInfo"]');
  const publicationDateStr = await publicationDateElement.evaluate(el => el.textContent);

  const publicationDate = publicationDateStr.split(', ')[1];

  const result = {title, author, publicationDate, series};

  await browser.close();

  return result;
}

const combine_title_and_series = ({title, series}) => {
  const [seriesName, seriesNumber] = series.split(' #');
  const formattedSeries = '(' + seriesName + ', #' + seriesNumber + ')';
  return title + ' ' + formattedSeries;
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

const main = async (url) => {

  if(!url || typeof url !== "string") return {};
  url = get_last_sub_dir_from_url(url);
  url = remove_query_string(url);
  url = remove_text_title(url);
  const book_id = remove_non_numeric_char_from_str(url);

  if(!book_id) return { statusCode: 500 };

  const result = await get_book_data_by_goodreads_id('2');
  if (result?.series) {
    result.title = combine_title_and_series(result);
  }

  return {
    statusCode: 200,
    body: { ...result, book_id: book_id}
  };

}

export default main;
