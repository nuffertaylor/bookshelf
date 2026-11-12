import importlib
import json
from unittest.mock import patch


def load(name):
    mod = importlib.import_module(f"lambdas.{name}.handler")
    return importlib.reload(mod)


def call(handler, db, payload):
    """Invoke a handler with a JSON body; returns (statusCode, inner body)."""
    with patch.object(handler, "_get_db", return_value=db):
        result = handler.lambda_handler({"body": json.dumps(payload)}, {})
    return result["statusCode"], json.loads(result["body"])["body"]
