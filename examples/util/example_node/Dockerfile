# Use an official Python runtime as parent image
FROM python:3.8

# Set working directory in container to /app
WORKDIR /app

# Copy whole dir
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run command to start app when container launches
# Also use exec so ctrl+c works
CMD exec python sil_node.py