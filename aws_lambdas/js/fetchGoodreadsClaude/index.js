import axios from 'axios';
import * as cheerio from 'cheerio';

const extractBookIdFromInput = (input) => {
  if (!input || typeof input !== "string") return null;

  // If it's already just a number, return it
  if (/^\d+$/.test(input.trim())) {
    return input.trim();
  }

  // Extract from URL
  const urlMatch = input.match(/goodreads\.com\/book\/show\/(\d+)/);
  if (urlMatch) {
    return urlMatch[1];
  }

  // Try to extract any numeric part
  const numericMatch = input.match(/(\d+)/);
  if (numericMatch) {
    return numericMatch[1];
  }

  return null;
};

const buildGoodreadsUrl = (bookId) => {
  return `https://www.goodreads.com/book/show/${bookId}`;
};

const fetchBookData = async (url) => {
  // Fetch the HTML page
  const response = await axios.get(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
  });

  const html = response.data;
  const $ = cheerio.load(html);

  // Try to extract from JSON-LD structured data first (most reliable)
  let bookData = { title: null, author: null, year: null };

  const jsonLdScript = $('script[type="application/ld+json"]').html();
  if (jsonLdScript) {
    try {
      const parsed = JSON.parse(jsonLdScript);
      bookData.title = parsed.name || null;
      bookData.author = parsed.author?.[0]?.name || null;

      // Try to extract year from datePublished
      if (parsed.datePublished) {
        const yearMatch = parsed.datePublished.match(/\d{4}/);
        if (yearMatch) {
          bookData.year = yearMatch[0];
        }
      }
    } catch (error) {
      console.error("Failed to parse JSON-LD:", error);
    }
  }

  // Fallback: Try to extract from HTML elements if JSON-LD didn't work
  if (!bookData.title) {
    bookData.title = $('[data-testid="bookTitle"]').first().text().trim() || null;
  }

  if (!bookData.author) {
    bookData.author = $('[data-testid="name"]').first().text().trim() || null;
  }

  if (!bookData.year) {
    const pubInfo = $('[data-testid="publicationInfo"]').first().text().trim();
    if (pubInfo) {
      // Extract year from publication info (e.g., "First published January 1, 2020")
      const yearMatch = pubInfo.match(/\d{4}/);
      if (yearMatch) {
        bookData.year = yearMatch[0];
      }
    }
  }

  return bookData;
};

export const handler = async (event) => {
  try {
    // Extract book_id from event
    // Support both direct book_id and url fields
    const input = event.book_id || event.url;

    if (!input) {
      return {
        statusCode: 400,
        body: JSON.stringify({
          error: "Missing book_id or url parameter"
        })
      };
    }

    const bookId = extractBookIdFromInput(input);

    if (!bookId) {
      return {
        statusCode: 400,
        body: JSON.stringify({
          error: "Could not extract valid book ID from input"
        })
      };
    }

    const url = buildGoodreadsUrl(bookId);

    // Fetch book data
    const bookData = await fetchBookData(url);

    return {
      statusCode: 200,
      body: JSON.stringify({
        book_id: bookId,
        title: bookData.title,
        author: bookData.author,
        year: bookData.year
      })
    };

  } catch (error) {
    console.error("Error fetching book data:", error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        error: error.message || "Internal server error"
      })
    };
  }
};

// Local testing
// Uncomment to test locally via "node index.js"
// const result = await handler({
//   book_id: "49021976"
// });
// console.log(JSON.stringify(result, null, 2));
