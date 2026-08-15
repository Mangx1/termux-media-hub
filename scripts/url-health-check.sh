#!/usr/bin/env bash

set -u

INPUT="data/urls.txt"
OUTPUT="output/health-report.csv"
SUMMARY="output/health-summary.txt"

mkdir -p output

echo "url,status,http_code,content_type,response_time,final_url" > "$OUTPUT"

total=0
up=0
down=0
total_time=0

if [ ! -f "$INPUT" ]; then
    echo "Input file not found: $INPUT"
    exit 1
fi

while IFS= read -r url || [ -n "$url" ]; do
    case "$url" in
        ""|\#*) continue ;;
    esac

    total=$((total + 1))

    echo "Checking: $url"

    result=$(curl \
        -L \
        -sS \
        -o /dev/null \
        --max-time 20 \
        -w '%{http_code}|%{content_type}|%{time_total}|%{url_effective}' \
        "$url" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$result" ]; then
        echo "\"$url\",\"DOWN\",\"000\",\"\",\"\",\"\"" >> "$OUTPUT"
        down=$((down + 1))
        continue
    fi

    IFS='|' read -r code content_type response_time final_url <<< "$result"

    if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then
        status="UP"
        up=$((up + 1))
        total_time=$(awk "BEGIN {print $total_time + $response_time}")
    else
        status="DOWN"
        down=$((down + 1))
    fi

    printf '"%s","%s","%s","%s","%s","%s"\n' \
        "$url" \
        "$status" \
        "$code" \
        "$content_type" \
        "$response_time" \
        "$final_url" >> "$OUTPUT"

done < "$INPUT"

if [ "$total" -gt 0 ]; then
    success_rate=$(awk "BEGIN {printf \"%.1f\", ($up / $total) * 100}")
else
    success_rate="0.0"
fi

if [ "$up" -gt 0 ]; then
    avg_response=$(awk "BEGIN {printf \"%.3f\", $total_time / $up}")
else
    avg_response="0.000"
fi

cat > "$SUMMARY" <<REPORT
TERMUX MEDIA HUB
========================
TOTAL URL    : $total
UP           : $up
DOWN         : $down
SUCCESS RATE : ${success_rate}%
AVG RESPONSE : ${avg_response}s
========================
REPORT

echo
cat "$SUMMARY"
echo
cat "$OUTPUT"
