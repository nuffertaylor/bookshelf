from dynamodb_dao import putUser, putAuthtoken, getUser
import hashlib
import json
import random
import time

def lambda_handler(event, context):
    if("requestType" not in event.keys()):
        return httpResult(400, "No requestType provided")
    if(event["requestType"] == "register"):
        if(event["username"] and event["password"] and event["email"]):
            if(not getUser(event["username"])):
                salt = genSalt()
                hashedPassword = hashAndSalt(event["password"], salt)
                if("ip" not in event.keys()):
                    event["ip"] = ""
                authtoken = registerUser(event["username"], hashedPassword, salt, event["email"], event["ip"])
                return httpResult(200, {"username" : event["username"], "authtoken" : authtoken})
            else:
                return httpResult(403, "username '" + event["username"] + "' already taken")
        else:
            return httpResult(403, "invalid input, missing username, password, or email")
    elif(event["requestType"] == "login"):
        if(event["username"] and event["password"]):
            userData = getUser(event["username"])
            if(userData):
                if(hashAndSalt(event["password"], userData["salt"]) == userData["hashedPassword"]):
                    expiry = get7DaysFromNow()
                    authtoken = genSalt()
                    if(putAuthtoken(userData["username"], authtoken, expiry)):
                        return httpResult(200, {"username" : userData["username"], "authtoken" : authtoken})
                    else:
                        return httpResult(400, "something went wrong")
                else:
                    return httpResult(403, "invalid password")
            else:
                return httpResult(403, "username '" + event["username"] + "' does not exist")
        else:
            return httpResult(403, "invalid input, missing username or password")
    else:
        return httpResult(400, "'" + event["requestType"] + "' is an invalid requestType")

def genSalt():
    return ''.join(random.choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ") for i in range(32))
    
def hashAndSalt(password, salt):
    return hashlib.sha512(password.encode('utf-8') + salt.encode('utf-8')).hexdigest()

def registerUser(username, hashedPassword, salt, email, ip):
    expiry = get24HoursFromNow()
    authtoken = genSalt()
    if(putUser(username, hashedPassword, salt, email, ip, authtoken, expiry)):
        return authtoken
    else:
        return False

def get24HoursFromNow():
    return int( time.time() ) + (1000*60*24)
    
def get7DaysFromNow():
    return int( time.time() ) + (7*1000*60*24)

def httpResult(statusCode, body):
    return {"statusCode" : statusCode, "body" : body}