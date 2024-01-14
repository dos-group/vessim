# Use an official Python runtime as parent image
FROM python:3.8

# Install sysbench utiliy for benchmark
RUN apt-get update && apt-get install -y sysbench
# Set working directory in container to /app
WORKDIR /app

# Copy dependency and src contents into the container at /app
COPY ./node_api_server.py .
COPY ./virtual_node ./virtual_node

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r virtual_node/requirements.txt

# Run command to start app when container launches with HOST_POST var
# Also use exec so ctrl+c works
CMD exec python ./virtual_node/v_node_api_server.py $HOST_PORT