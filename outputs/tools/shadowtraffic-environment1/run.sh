#!/usr/bin/env bash
# Live run: produces real Avro-serialized events to datagen.users.enterprise
# on the target Confluent Cloud cluster until stopped (Ctrl+C).
set -euo pipefail
cd "$(dirname "$0")"

docker run --rm \
  --env-file license.env \
  --env-file .env \
  -v "$(pwd)/config/shadowtraffic-config.json:/home/config.json" \
  -v "$(pwd)/config/client.properties:/home/config/client.properties" \
  shadowtraffic/shadowtraffic:latest \
  --config /home/config.json
