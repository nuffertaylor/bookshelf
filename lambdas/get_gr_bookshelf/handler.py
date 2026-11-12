from bookshelf.http import http_result


def lambda_handler(event, context):
    return http_result(410, {"error": "Goodreads RSS is no longer available. Upload your Goodreads export instead."})
