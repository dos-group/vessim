import sys
from http_client import HTTPClient, HTTPClientError


# Get server address from command line arguments, default to http://localhost
if len(sys.argv) > 1:
    server_address = sys.argv[1]
else:
    server_address = 'http://localhost'

# Create HTTPClient instance and call methods with server address, route, and data
client = HTTPClient(server_address)
route = '/data'
try:
    data = client.GET(route)
    print(data)
except HTTPClientError as e:
    print(e)

data_to_put = {'name': 'John', 'age': 30}
try:
    client.PUT(route, data_to_put)
except HTTPClientError as e:
    print(e)
