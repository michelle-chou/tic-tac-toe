import json as JSON


class RequestSpecHelper:
    # Parse JSON response to python dict
    def json(self):
        return JSON.loads(self.response.data)
