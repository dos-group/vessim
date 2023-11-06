import requests
import json
from typing import Any, Dict


class HttpClient:
    """Class for making HTTP requests to the Vessim API server.

    Args:
        server_address: The address of the server to connect to.
            e.g. http://localhost
    """

    def __init__(self, server_address: str, timeout: float = 5) -> None:
        self.server_address = server_address
        self.timeout = timeout

    def get(self, route: str) -> dict:
        """Sends a GET request to the server and retrieves data.

        Args:
            route: The path of the endpoint to send the request to.

        Raises:
            HTTPError: If response code is != 200.

        Returns:
            A dictionary containing the response.
        """
        response = requests.get(self.server_address + route, timeout=self.timeout)
        if response.status_code != 200:
            response.raise_for_status()
        data = response.json()  # assuming the response data is in JSON format
        return data

    def put(self, route: str, data: Dict[str, Any] = {}) -> None:
        """Sends a PUT request to the server to update data.

        Args:
            route: The path of the endpoint to send the request to.
            data: The data to be updated, in dictionary format.

        Raises:
            HTTPError: If response code is != 200.
        """
        headers = {"Content-type": "application/json"}
        response = requests.put(
            self.server_address + route,
            data=json.dumps(data),
            headers=headers,
            timeout=self.timeout,
        )
        if response.status_code != 200:
            response.raise_for_status()
