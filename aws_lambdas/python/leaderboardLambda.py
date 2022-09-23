from cockroachdb_dao import CockroachDAO
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def lambda_handler(event, context):
  return {
    "statusCode": 200,
    "body" : db.get_leaderboard()
  }