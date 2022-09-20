import main from "./fetchGRDataFromBookUrl.js";

export const handler = async (event) => {
  const book = await main(event.url);
  const response = {
    statusCode: 200,
    body: book
  };
  return response;
};

//aws cli command to upload:
/*
zip -r lambda.zip .
aws lambda update-function-code --function-name loginRegister \
--zip-file fileb://~/projects/bookshelf/aws_lambdas/js/loginRegister/lambda.zip
*/