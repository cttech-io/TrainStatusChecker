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
all_disruptions=""
while IFS= read -r line; do
    disruption=$(echo "$line" | sed -n 's/.*\(incident: \(Stansted Express\|Cambridge\)[[:space:]]*[^"]*\)".*/\1/p')
    if [ -n "$disruption" ]; then
        all_disruptions+="$disruption"$'\n'
    fi
done <<< "$html"

# Remove the trailing newline character
all_disruptions=$(echo "$all_disruptions" | sed '/^$/d')

# Print all disruptions
echo "$all_disruptions"
# Check if any disruptions were found
if [[ -n "$disruptions" ]]; then
echo "$disruptions"
else
  echo "No disruptions found."
fi