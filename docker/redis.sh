#!/bin/sh
set -eu
exec redis-server --requirepass "$(cat /run/secrets/redis_password)" --maxmemory 384mb --maxmemory-policy noeviction --save '' --appendonly no
