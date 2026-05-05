"""
Mock AWS Lambda context object for local testing.
"""

class MockLambdaContext:
    """Simulates the AWS Lambda context object passed to lambda_handler."""

    def __init__(self, function_name="local-test"):
        self.function_name = function_name
        self.memory_limit_in_mb = 128
        self.invoked_function_arn = f"arn:aws:lambda:us-east-1:000000000000:function:{function_name}"
        self.aws_request_id = "local-request-id"
        self.log_group_name = f"/aws/lambda/{function_name}"
        self.log_stream_name = "local"

    def get_remaining_time_in_millis(self):
        """Returns remaining execution time in milliseconds."""
        return 300000  # 5 minutes
