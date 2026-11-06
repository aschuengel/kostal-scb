#!/bin/bash
docker run --name kostal-scb \
    -p 80:8000 \
    --env-file .env \
    --restart always \
    -d \
    aschuengel/kostal-scb:latest