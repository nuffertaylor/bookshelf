import puppeteer from 'puppeteer';
// Or import puppeteer from 'puppeteer-core';

const get_book_data_by_goodreads_id = async (goodreads_id) => {
  // Launch the browser and open a new blank page
  const browser = await puppeteer.launch({headless: true});
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

const result = await get_book_data_by_goodreads_id('2');
console.log(result);
if (result?.series) {
  console.log(combine_title_and_series(result));
}