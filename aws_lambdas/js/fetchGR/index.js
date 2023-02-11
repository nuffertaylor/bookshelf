import main from "./fetchGRDataFromBookUrl.js";

export const handler = async (event) => {
  const book = await main(event.url);
  const response = {
    statusCode: 200,
    body: book
  };
  return response;
};

//test locally via "node index.js"
const res = await handler({url :
  //insert test url here
  "https://www.goodreads.com/book/show/11557.Swan_Song"
});
console.log(res);

//aws cli command to upload:
/*
zip -r lambda.zip .
aws lambda update-function-code --function-name fetchGRDataFromBookUrl \
--zip-file fileb://~/projects/bookshelf/aws_lambdas/js/fetchGR/lambda.zip
*/