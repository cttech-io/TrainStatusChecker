#!/bin/bash

# URL of the train service status page
url="https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"  

# Fetch the webpage content
html=$(curl -s "$url")

# Check if the request was successful
if [[ $? -ne 0 ]]; then
  echo "Error fetching webpage: $url"
  exit 1
fi

# Extract disruption information using grep and sed
disruptions=$(echo "$html" | sed -n 's/.*\(incident: Stansted Express[[:space:]]*[^"]*\)".*/\1/p; s/.*\(incident: Cambridge[[:space:]]*[^"]*\)".*/\1/p')

# Check if any disruptions were found
if [[ -n "$disruptions" ]]; then
echo "$disruptions"
else
  echo "No disruptions found."
fi