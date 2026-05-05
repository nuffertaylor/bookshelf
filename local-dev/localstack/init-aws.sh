#!/bin/bash

# Wait for LocalStack to be fully ready
echo "Waiting for LocalStack to be ready..."
sleep 10

# Set LocalStack endpoint
export AWS_ENDPOINT_URL=http://localstack:4566

# Create S3 bucket for bookshelf spines
echo "Creating S3 bucket: bookshelf-spines"
aws --endpoint-url=$AWS_ENDPOINT_URL s3 mb s3://bookshelf-spines

# Create DynamoDB table (mirrors current AWS table structure)
echo "Creating DynamoDB table: bookshelf"
aws --endpoint-url=$AWS_ENDPOINT_URL dynamodb create-table \
  --table-name bookshelf \
  --attribute-definitions \
    AttributeName=title,AttributeType=S \
    AttributeName=book_id,AttributeType=S \
  --key-schema \
    AttributeName=title,KeyType=HASH \
    AttributeName=book_id,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST

echo "LocalStack initialization complete!"
