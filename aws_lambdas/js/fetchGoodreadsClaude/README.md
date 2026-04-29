# fetchGoodreadsClaude Lambda

AWS Lambda function that extracts book information from Goodreads using traditional web scraping.

## Features

- Accepts either a numeric book ID or a full Goodreads URL
- Extracts: title, author, and year originally published
- Uses axios and cheerio for HTML parsing
- Tries JSON-LD structured data first, falls back to HTML selectors
- Returns structured JSON response

## Input

The lambda accepts an event with either:
- `book_id`: A numeric Goodreads book ID (e.g., "143511")
- `url`: A full Goodreads URL (e.g., "https://www.goodreads.com/book/show/143511.Under_Western_Eyes")

Example:
```json
{
  "book_id": "143511"
}
```

or

```json
{
  "url": "https://www.goodreads.com/book/show/143511.Under_Western_Eyes"
}
```

## Output

Returns a JSON response:

```json
{
  "statusCode": 200,
  "body": {
    "book_id": "143511",
    "title": "Under Western Eyes",
    "author": "Joseph Conrad",
    "year": "1911"
  }
}
```

## Setup

1. Install dependencies:
```bash
npm install
```

## Local Testing

Uncomment the test code at the bottom of `index.js` and run:
```bash
node index.js
```

## Deployment

1. Create a deployment package:
```bash
zip -r lambda.zip .
```

2. Deploy to AWS Lambda:
```bash
aws lambda update-function-code --function-name fetchGoodreadsClaude \
  --zip-file fileb://lambda.zip
```

## Requirements

- Node.js 18.x or later
- AWS Lambda execution role with appropriate permissions
