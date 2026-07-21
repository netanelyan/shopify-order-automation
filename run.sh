#!/bin/bash
# run.sh — parse CSV(s) and build docx in one command
#
# Usage:
#   ./run.sh input1.csv [input2.csv ...] output.docx
#
# Example:
#   ./run.sh orders_july19.csv output.docx
#   ./run.sh file1.csv file2.csv output.docx

if [ "$#" -lt 2 ]; then
  echo "Usage: ./run.sh input1.csv [input2.csv ...] output.docx"
  exit 1
fi

OUTPUT="${@: -1}"
CSV_FILES="${@:1:$#-1}"
JSON_FILE="${OUTPUT%.docx}.json"

echo "→ Parsing CSVs..."
python3 parse_orders.py $CSV_FILES -o "$JSON_FILE"
if [ $? -ne 0 ]; then echo "✗ Parsing failed"; exit 1; fi

echo "→ Building docx..."
node build_docx.js "$JSON_FILE" "$OUTPUT"
echo "→ Done: $OUTPUT"
