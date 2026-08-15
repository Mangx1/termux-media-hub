#!/usr/bin/env python3

import csv
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

INPUT = "output/playlist-report.csv"
OUTPUT = "output/retry-report.csv"

TIMEOUT = 12
WORKERS = 10

USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
    "VLC/3.0.21 LibVLC/3.0.21",
    "ExoPlayerDemo/1.0",
]


def test(url, ua):
    start = time.time()

    cmd = [
        "curl",
        "-L",
        "-sS",
        "--max-time", str(TIMEOUT),
        "--connect-timeout", "6",
        "-A", ua,
        "-o", "/dev/null",
        "-w", "%{http_code}|%{size_download}|%{content_type}",
        url,
    ]

    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        elapsed = time.time() - start

        parts = p.stdout.strip().split("|")

        code = int(parts[0]) if parts and parts[0].isdigit() else 0
        size = parts[1] if len(parts) > 1 else "0"
        content_type = parts[2] if len(parts) > 2 else ""

        if 200 <= code < 400 and float(size or 0) > 0:
            status = "ONLINE"

        elif code == 403:
            status = "BLOCKED"

        elif code == 404:
            status = "DEAD"

        elif code == 503:
            status = "TEMPORARY"

        elif code == 0:
            status = "CONNECTION"

        else:
            status = "ERROR"

        return {
            "status": status,
            "http_code": code,
            "bytes": size,
            "content_type": content_type,
            "time": f"{elapsed:.3f}",
            "ua": ua,
        }

    except Exception as e:
        return {
            "status": "CONNECTION",
            "http_code": 0,
            "bytes": 0,
            "content_type": "",
            "time": f"{time.time() - start:.3f}",
            "ua": ua,
        }


def check(row):
    url = row["url"]

    best = None

    for ua in USER_AGENTS:
        result = test(url, ua)

        if best is None:
            best = result

        if result["status"] == "ONLINE":
            best = result
            break

        if result["status"] == "BLOCKED":
            best = result

    return {
        "channel": row["channel"],
        "type": row["type"],
        "url": url,
        "original_status": row["status"],
        "original_detail": row["detail"],
        "retry_status": best["status"],
        "http_code": best["http_code"],
        "bytes": best["bytes"],
        "content_type": best["content_type"],
        "response_time": best["time"],
        "user_agent": best["ua"],
    }


def main():
    rows = []

    with open(INPUT, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row["status"] == "ERROR":
                rows.append(row)

    print("========================================")
    print("       TERMUX MEDIA HUB")
    print("       ERROR RETRY SCANNER")
    print("========================================")
    print()
    print(f"Errors to retry : {len(rows)}")
    print()

    results = [None] * len(rows)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:

        futures = {
            executor.submit(check, row): i
            for i, row in enumerate(rows)
        }

        done = 0

        for future in as_completed(futures):
            i = futures[future]

            try:
                results[i] = future.result()
            except Exception:
                results[i] = {
                    "channel": rows[i]["channel"],
                    "type": rows[i]["type"],
                    "url": rows[i]["url"],
                    "original_status": "ERROR",
                    "original_detail": "UNKNOWN",
                    "retry_status": "CONNECTION",
                    "http_code": 0,
                    "bytes": 0,
                    "content_type": "",
                    "response_time": "0",
                    "user_agent": "",
                }

            done += 1

            x = results[i]

            print(
                f"[{done}/{len(rows)}] "
                f"{x['retry_status']:10} "
                f"{x['channel'][:35]}"
            )

    with open(
        OUTPUT,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        fields = [
            "channel",
            "type",
            "url",
            "original_status",
            "original_detail",
            "retry_status",
            "http_code",
            "bytes",
            "content_type",
            "response_time",
            "user_agent",
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(results)

    counts = {}

    for x in results:
        counts[x["retry_status"]] = counts.get(
            x["retry_status"], 0
        ) + 1

    print()
    print("========================================")
    print("          RETRY COMPLETE")
    print("========================================")

    for key in [
        "ONLINE",
        "DEAD",
        "BLOCKED",
        "TEMPORARY",
        "CONNECTION",
        "ERROR",
    ]:
        print(
            f"{key:12}: {counts.get(key, 0)}"
        )

    print("========================================")
    print()
    print(f"Report: {OUTPUT}")


if __name__ == "__main__":
    main()
