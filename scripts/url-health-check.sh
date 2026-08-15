#!/usr/bin/env bash

set -u

INPUT="data/urls.txt"
OUTPUT="output/health-report.csv"

mkdir -p output

echo "url,status,http_code,content_type,response_time,final_url" > "$OUTPUT"

if [ ! -f "$INPUT" ]; then
    echo "Input file not found: $INPUT"
    exit 1
fi

while IFS= read -r url || [ -n "$url" ]; do
    case "$url" in
        ""|\#*) continue ;;
    esac

    echo "Checking: $url"

    result=$(curl \
        -L \
        -sS \
        -o /dev/null \
        --max-time 20 \
        -w '%{http_code}|%{content_type}|%{time_total}|%{url_effective}' \
        "$url" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$result" ]; then
        echo "\"$url\",DOWN,000,,,\"\"" >> "$OUTPUT"
        continue
    fi

    IFS='|' read -r code content_type response_time final_url <<< "$result"

    if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then
        status="UP"
    else
        status="DOWN"
    fi

    printf '"%s","%s","%s","%s","%s","%s"\n' \
        "$url" \
        "$status" \
        "$code" \
        "$content_type" \
        "$response_time" \
        "$final_url" >> "$OUTPUT"

done < "$INPUT"

echo
echo "================================"
echo " URL HEALTH CHECK COMPLETE"
echo "================================"
cat "$OUTPUT"
echo "================================"
