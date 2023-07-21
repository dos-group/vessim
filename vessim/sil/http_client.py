import requests
import json
from typing import Any, Dict


class HTTPClientError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message
        super().__init__(f"HTTP client error (status code: {status_code}): {message}")


class HTTPClient:
    """Class for making HTTP requests to the VESSIM API server.

    Args:
        server_address: The address of the server to connect to.
            e.g. http://localhost
    """

    def __init__(self, server_address: str) -> None:
        self.server_address = server_address

    def get(self, route: str) -> dict:
        """Sends a GET request to the server and retrieves data.

        Args:
            route: The path of the endpoint to send the request to.

        Raises:
            HTTPClientError if the data could not be retrieved from route

        Returns:
            A dictionary containing the response.
        """
        response = requests.get(self.server_address + route)
        if response.status_code == 200:
            data = response.json() # assuming the response data is in JSON format
            return data

        raise HTTPClientError(
            response.status_code,
            f'Failed to retrieve data from {route}'
        )

    def put(self, route: str, data: Dict[str, Any]) -> None:
        """Sends a PUT request to the server to update data.

        Raises:
            HTTPClientError if the data could not be updated at route

        Args:
            route: The path of the endpoint to send the request to.
            data: The data to be updated, in dictionary format.
        """
        headers = {'Content-type': 'application/json'}
        response = requests.put(
            self.server_address + route,
            data=json.dumps(data),
            headers=headers
        )
        if response.status_code != 200:
            raise HTTPClientError(
                response.status_code,
                f'Failed to update data at {route}'
            )

