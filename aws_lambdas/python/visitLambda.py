from cockroachdb_dao import CockroachDAO
import time
import os
db = CockroachDAO(os.getenv('DATABASE_URL'))

def build_return(code, msg):
  return {"statusCode" : code, "body" : msg}

def lambda_handler(event, context):
  if("ip" not in event): return build_return(403, "missing ip")
  previous_visitor = db.get_visitor_by_ip(event["ip"])
  if(not previous_visitor):
    if("os" not in event): event["os"] = "unknown"
    if("browser" not in event): event["browser"] = "unknown"
    if(db.add_visitor(event)): return build_return(200, "success")
    return build_return(500, "Error logging new visitor")
  #only log it as a new visit after ten minutes
  WAITING_PERIOD = 60*10
  if(int(previous_visitor["timestamp"]) >  int(time.time()) - WAITING_PERIOD): return build_return(200, "unlogged, repeat visit")
  if(db.update_visit_count(previous_visitor["visitor_id"], previous_visitor["num_visits"])): return build_return(200, "success")
  return build_return(500, "Error logging visit")
