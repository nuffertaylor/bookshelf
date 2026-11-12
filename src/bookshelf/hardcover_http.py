from bookshelf import hardcover_client
from bookshelf.http import http_result


def error_response(e):
    """Map Hardcover client exceptions to HTTP responses for the library endpoints."""
    if isinstance(e, hardcover_client.HardcoverReauthRequired):
        # 401 here means "reconnect Hardcover"; the site session itself is still valid.
        return http_result(401, {"error": "hardcover_reauth_required"})
    if isinstance(e, hardcover_client.HardcoverRateLimited):
        return http_result(429, {"error": "Hardcover rate limit reached, please try again shortly."})
    print("hardcover error: status=" + str(getattr(e, "status", None)))
    return http_result(502, {"error": "Could not reach Hardcover, please try again shortly."})
