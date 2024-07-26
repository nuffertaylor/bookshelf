import main from './goodreads-puppeteer-scraper.js';

export const handler = async (event) => {
  return await main(event.url);
};

// zip -r fetchGrPuppeteer.zip .
// maybe use the layer? https://github.com/shelfio/chrome-aws-lambda-layer