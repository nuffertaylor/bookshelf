import main from "./fetchGRDataFromBookUrl.js";
import * as fs from 'node:fs';

export const handler = async (event) => {
  return await main(event.url);
};

const storeData = (data, path) => {
  try {
    fs.writeFileSync(path, JSON.stringify(data))
  } catch (err) {
    console.error(err)
  }
}

let books = [];
for(let i = 0; i < 1001; i++) {
  const res = await handler({url : i.toString()});
  if(res.statusCode === 200) books.push(res.body);
}
storeData(books, "1-1000GR.json");



// test locally via "node index.js"
// const res = await handler({url :
//   //insert test url here
//   "https://www.goodreads.com/book/show/19161852-the-fifth-season"
// });
// console.log(res);

//aws cli command to upload:
/*
zip -r lambda.zip .
aws lambda update-function-code --function-name fetchGRDataFromBookUrl \
--zip-file fileb://~/projects/bookshelf/aws_lambdas/js/fetchGR/lambda.zip
*/