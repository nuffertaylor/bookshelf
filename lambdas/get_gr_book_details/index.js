const axios = require('axios');
const cheerio = require('cheerio');

const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
};

const httpResult = (statusCode, body) => ({
  statusCode,
  headers: CORS_HEADERS,
  body: JSON.stringify({ statusCode, body }),
});

const extractBookId = (input) => {
  if (!input || typeof input !== 'string') return null;
  if (/^\d+$/.test(input.trim())) return input.trim();
  const urlMatch = input.match(/goodreads\.com\/book\/show\/(\d+)/);
  if (urlMatch) return urlMatch[1];
  const numericMatch = input.match(/(\d+)/);
  return numericMatch ? numericMatch[1] : null;
};

const decodeHtmlEntities = (str) => {
  if (!str) return str;
  return str
    .replace(/&amp;/g, '&')
    .replace(/&apos;/g, "'")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>');
};

const fetchBookData = async (bookId) => {
  const url = `https://www.goodreads.com/book/show/${bookId}`;
  const response = await axios.get(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    },
  });

  const $ = cheerio.load(response.data);
  const bookData = { title: null, author: null, pubDate: null };

  const jsonLdScript = $('script[type="application/ld+json"]').text();
  if (jsonLdScript) {
    try {
      const parsed = JSON.parse(jsonLdScript);
      bookData.title = parsed.name || null;
      bookData.author = parsed.author?.[0]?.name || null;
      if (parsed.datePublished) {
        const yearMatch = parsed.datePublished.match(/\d{4}/);
        if (yearMatch) bookData.pubDate = yearMatch[0];
      }
    } catch (e) {
      console.error('Failed to parse JSON-LD:', e);
    }
  }

  if (!bookData.title) {
    bookData.title = $('[data-testid="bookTitle"]').first().text().trim() || null;
  }
  if (!bookData.author) {
    bookData.author = $('[data-testid="name"]').first().text().trim() || null;
  }
  if (!bookData.pubDate) {
    const pubInfo = $('[data-testid="publicationInfo"]').first().text().trim();
    if (pubInfo) {
      const yearMatch = pubInfo.match(/\d{4}/);
      if (yearMatch) bookData.pubDate = yearMatch[0];
    }
  }

  return bookData;
};

exports.handler = async (event) => {
  const respond = (statusCode, body) =>
    process.env.AWS_SAM_LOCAL ? httpResult(statusCode, body) : { statusCode, body };

  const params = event.queryStringParameters || {};
  const input = params.url || params.book_id || event.url || event.book_id;

  if (!input) {
    return respond(400, { error: 'Missing url or book_id parameter' });
  }

  const bookId = extractBookId(input);
  if (!bookId) {
    return respond(400, { error: 'Could not extract valid book ID from input' });
  }

  try {
    const bookData = await fetchBookData(bookId);
    return respond(200, {
      book_id: bookId,
      title: decodeHtmlEntities(bookData.title),
      author: decodeHtmlEntities(bookData.author),
      pubDate: bookData.pubDate,
    });
  } catch (error) {
    console.error('Error fetching book data:', error);
    return respond(500, { book_id: bookId, error: error.message });
  }
};
