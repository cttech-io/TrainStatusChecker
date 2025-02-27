#!/bin/bash

# URL of the train service status page
url="https://www.nationalrail.co.uk/status-and-disruptions/?mode=train-operator-status"

# Train operators to monitor
train_operators=("Stansted Express" "Cambridge" "Greater Anglia")

# Fetch the webpage content
html=$(curl -s "$url")

# Check if the request was successful
if [[ $? -ne 0 ]]; then
  echo "Error fetching webpage: $url"
  exit 1
fi

disruptions=""

# Loop through train operators and extract disruptions
for operator in "${train_operators[@]}"; do
  operator_disruptions=$(echo "$html" | grep "incident: $operator" | sed -n 's/.*\(incident: '"$operator"'[^"]*\)".*/\1/p')
  if [[ -n "$operator_disruptions" ]]; then
    if [[ -n "$disruptions" ]]; then
      disruptions="$disruptions\n$operator_disruptions"
    else
      disruptions="$operator_disruptions"
    fi
  fi
done

# Check if any disruptions were found
if [[ -n "$disruptions" ]]; then
  echo "$disruptions"
else
  echo "No disruptions found."
fi