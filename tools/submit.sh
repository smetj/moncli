#!/bin/bash
curl -d username="default" -d password="changeme" --data-urlencode input="$1" localhost:6555
echo $1
