import main from "./fetchGRDataFromBookUrl.js";

export const handler = async (event) => {
  return await main(event.url);
};

/* test locally via "node index.js" */
// const res = await handler({url :
//   //insert test url here
//   "https://www.goodreads.com/book/show/55728061-and-then-she-vanished"
// });
// console.log(res);

//aws cli command to upload:
/*
zip -r lambda.zip .
aws lambda update-function-code --function-name fetchGRDataFromBookUrl \
--zip-file fileb://~/projects/bookshelf/aws_lambdas/js/fetchGR/lambda.zip
*/