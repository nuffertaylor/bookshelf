import hashlib
import os
import random
import time
from cockroachdb_dao import CockroachDAO 
db = CockroachDAO(os.getenv('DATABASE_URL'))

def lambda_handler(event, context):
  if("requestType" not in event.keys()): return httpResult(400, "No requestType provided")
  if("username" not in event.keys()): return httpResult(403, "invalid input, missing username")
  if("password" not in event.keys()): return httpResult(403, "invalid input, missing password")

  if(event["requestType"] == "register"):
    if("email" not in event.keys()): return httpResult(403, "invalid input, missing email")
    if("ip" not in event.keys()): event["ip"] = ""
    return handleRegister(event["username"], event["password"], event["email"], event["ip"])
  elif(event["requestType"] == "login"):
    return handleLogin(event["username"], event["password"])
  else:
    return httpResult(400, "'" + event["requestType"] + "' is an invalid requestType")

def genSalt():
  return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for i in range(32))
  
def hashAndSalt(password, salt):
  return hashlib.sha512(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()

def handleRegister(username, password, email, ip):
  if(db.get_user(username)): return httpResult(403, "username '" + username + "' is already taken")
  salt = genSalt()
  hashedPassword = hashAndSalt(password, salt)
  authtoken = registerUser(username, hashedPassword, salt, email, ip)
  return httpResult(200, {"username" : username, "authtoken" : authtoken})

def handleLogin(username, password):
  userData = db.get_user(username)
  if(not userData): return httpResult(403, "username '" + username + "' does not exist")
  if(hashAndSalt(password, userData["salt"]) != userData["hashedPassword"]):
    return httpResult(403, "invalid password")
  expiry = get7DaysFromNow()
  authtoken = genSalt()
  res = db.update_user_authtoken(username, authtoken, expiry)
  if(res):
    return httpResult(200, {"username" : res["username"], "authtoken" : res["authtoken"], "goodreads_id" : res["goodreads_id"]})
  return httpResult(400, "something went wrong, please try again later.")

def registerUser(username, hashedPassword, salt, email, ip):
  expiry = get7DaysFromNow()
  authtoken = genSalt()
  if(db.add_user({
    "username" : username,
    "hashedPassword" : hashedPassword,
    "email" : email,
    "authtoken" : authtoken,
    "expiry" : expiry,
    "salt" : salt,
    "ip" : ip
  })):
    return authtoken
  else:
    return False

def get24HoursFromNow():
  return str(int( time.time() ) + (1000*60*24))
  
def get7DaysFromNow():
  return str( int( time.time() ) + (7*1000*60*24))

def httpResult(statusCode, body):
  return {"statusCode" : statusCode, "body" : body}

# zip -r lambda.zip .
# aws lambda update-function-code --function-name loginRegister --zip-file fileb://~/projects/bookshelf/aws_lambdas/python/lambda.zip