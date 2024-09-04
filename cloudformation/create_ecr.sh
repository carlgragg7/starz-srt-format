#!/bin/bash

# Build Docker image
echo "Building Docker image transcribe:latest..."
docker build -t transcribe:latest .

# Tag the Docker image
docker tag transcribe:latest 780083371453.dkr.ecr.us-east-2.amazonaws.com/starz:latest

echo "Authenticating Docker with ECR..."
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 780083371453.dkr.ecr.us-east-2.amazonaws.com

docker push 780083371453.dkr.ecr.us-east-2.amazonaws.com/starz:latest
