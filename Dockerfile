# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
ffmpeg \
&& rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
COPY requirements.txt /app/
RUN pip install -r requirements.txt


# Copy the current directory contents into the container at /app
COPY . /app

RUN mkdir -p downloads/ compressed/ splits/ transcription/

# Run pytest to execute the tests
CMD ["python3", "-m", "src.main"]
