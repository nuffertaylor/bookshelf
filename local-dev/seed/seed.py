#!/usr/bin/env python3
"""
Seed the local development database and LocalStack S3 with test data.

Prerequisites (run once on host machine):
    pip install psycopg2-binary boto3

Containers must be running first:
    docker compose -f local-dev/docker-compose.yml up -d
"""
import json
import os
import sys
import time

try:
    import boto3
    import psycopg2
    from botocore.config import Config
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Run: pip install psycopg2-binary boto3")
    sys.exit(1)

S3_ENDPOINT = "http://localhost:4566"
S3_BUCKET = "bookshelf-spines"
DB_URL = "postgresql://postgres:dev@localhost:5432/bookshelf"

SEED_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(SEED_DIR, "images")
DATA_FILE = os.path.join(SEED_DIR, "bookshelf_data.json")


def get_content_type(filename):
    return "image/png" if filename.endswith(".png") else "image/jpeg"


def seed_s3():
    print("Setting up S3...")
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
        config=Config(signature_version="s3v4"),
    )

    try:
        s3.head_bucket(Bucket=S3_BUCKET)
        print(f"  Bucket '{S3_BUCKET}' already exists.")
    except Exception:
        s3.create_bucket(Bucket=S3_BUCKET)
        print(f"  Created bucket '{S3_BUCKET}'.")

    s3.put_bucket_cors(
        Bucket=S3_BUCKET,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET"],
                    "AllowedOrigins": ["*"],
                    "MaxAgeSeconds": 3000,
                }
            ]
        },
    )
    print(f"  CORS policy applied to '{S3_BUCKET}'.")

    names = os.listdir(IMAGES_DIR)
    print(f"  Uploading {len(names)} images...")
    for name in names:
        with open(os.path.join(IMAGES_DIR, name), "rb") as f:
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=name,
                Body=f.read(),
                ContentType=get_content_type(name),
            )
    print(f"  Done — {len(names)} images uploaded to s3://{S3_BUCKET}/")


def seed_db():
    print("Seeding database...")
    with open(DATA_FILE) as f:
        payload = json.load(f)

    books = [book for group in payload["body"]["found"] for book in group]
    print(f"  Inserting {len(books)} book records...")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    inserted = skipped = errors = 0

    for book in books:
        try:
            cur.execute(
                """
                INSERT INTO bookshelf (
                    upload_id, book_id, title, author, dimensions,
                    domcolor, filename, genre, isbn, isbn13,
                    pubdate, submitter, rating, flagged, timestamp
                ) VALUES (
                    %(upload_id)s, %(book_id)s, %(title)s, %(author)s, %(dimensions)s,
                    %(domColor)s, %(fileName)s, %(genre)s, %(isbn)s, %(isbn13)s,
                    %(pubDate)s, %(submitter)s, %(rating)s, %(flagged)s, %(timestamp)s
                )
                ON CONFLICT DO NOTHING
                """,
                {
                    **book,
                    "book_id": int(book["book_id"]),
                    "timestamp": int(time.time()),
                },
            )
            conn.commit()
            inserted += cur.rowcount
            skipped += 1 - cur.rowcount
        except Exception as e:
            conn.rollback()
            errors += 1
            print(f"  Warning: skipped {book.get('fileName')}: {e}")

    cur.close()
    conn.close()
    print(f"  Inserted {inserted}, skipped {skipped} duplicates, {errors} errors.")


if __name__ == "__main__":
    seed_s3()
    seed_db()
    print("\nDone! Local environment seeded with test data.")
