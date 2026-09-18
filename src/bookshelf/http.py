import json


def parse_event(event):
    """Normalize an API Gateway event to a flat dict of request parameters."""
    if event.get("body"):
        body = event["body"]
        return json.loads(body) if isinstance(body, str) else body
    if event.get("queryStringParameters"):
        return event["queryStringParameters"]
    return event


def http_result_raw(status_code, body_dict):
    """Use when the frontend reads fields directly from the parsed response (not via .body)."""
    return {
        "statusCode": status_code,
        "body": json.dumps(body_dict),
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
    }


def http_result(status_code, body):
    return {
        "statusCode": status_code,
        "body": json.dumps({"statusCode": status_code, "body": body}),
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
    }
