#!/usr/bin/env python3

import csv
import os
import subprocess
import time
from urllib.parse import urljoin

INPUT = "data/urls.txt"
OUTPUT = "output/m3u8-report.csv"
TIMEOUT = 20


def curl_get(url, text_body=True):
    start = time.time()

    args = [
        "curl",
        "-L",
        "-sS",
        "--max-time", str(TIMEOUT),
        "-A", "Mozilla/5.0",
        "-w", "\n__HTTP__%{http_code}|%{url_effective}",
    ]

    if not text_body:
        args += ["-o", "/dev/null"]

    args.append(url)

    result = subprocess.run(
        args,
        capture_output=True,
        text=False
    )

    elapsed = time.time() - start

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        return None, 0, "", elapsed, error

    marker = b"\n__HTTP__"

    if marker not in result.stdout:
        return None, 0, "", elapsed, "Invalid curl response"

    body, meta = result.stdout.rsplit(marker, 1)
    meta = meta.decode("utf-8", errors="replace").strip()

    try:
        code, final_url = meta.split("|", 1)
        code = int(code)
    except Exception:
        return None, 0, "", elapsed, "Invalid HTTP metadata"

    if text_body:
        body = body.decode("utf-8", errors="replace")
    else:
        body = ""

    return body, code, final_url, elapsed, ""


def check_m3u8(url):
    body, code, final_url, elapsed, error = curl_get(url)

    if body is None:
        return "DOWN", "CURL_ERROR", code, elapsed, error

    if code < 200 or code >= 400:
        return "DOWN", "HTTP_ERROR", code, elapsed, ""

    if "#EXTM3U" not in body[:2000]:
        return "DOWN", "NOT_M3U8", code, elapsed, ""

    lines = [x.strip() for x in body.splitlines() if x.strip()]

    # Master playlist
    if "#EXT-X-STREAM-INF" in body:
        variant = None

        for i, line in enumerate(lines):
            if line.startswith("#EXT-X-STREAM-INF"):
                for candidate in lines[i + 1:]:
                    if not candidate.startswith("#"):
                        variant = candidate
                        break

                if variant:
                    break

        if variant:
            variant_url = urljoin(final_url, variant)

            vbody, vcode, vfinal, velapsed, verr = curl_get(variant_url)

            if vbody is None:
                return "DOWN", "VARIANT_ERROR", vcode, elapsed + velapsed, verr

            if vcode < 200 or vcode >= 400:
                return "DOWN", "VARIANT_HTTP_ERROR", vcode, elapsed + velapsed, variant_url

            if "#EXTM3U" not in vbody[:2000]:
                return "DOWN", "INVALID_VARIANT", vcode, elapsed + velapsed, variant_url

            body = vbody
            final_url = vfinal
            elapsed += velapsed

    # Find media segment
    segment = None

    for line in body.splitlines():
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        segment = line
        break

    if not segment:
        return "DOWN", "NO_SEGMENT", code, elapsed, ""

    segment_url = urljoin(final_url, segment)

    _, scode, _, selapsed, _ = curl_get(segment_url, text_body=False)

    elapsed += selapsed

    if 200 <= scode < 400:
        return "UP", "M3U8_OK_SEGMENT_OK", scode, elapsed, segment_url

    return "DOWN", "SEGMENT_ERROR", scode, elapsed, segment_url


def main():
    os.makedirs("output", exist_ok=True)

    urls = []

    with open(INPUT, encoding="utf-8") as f:
        for line in f:
            url = line.strip()

            if not url or url.startswith("#"):
                continue

            if url not in urls:
                urls.append(url)

    results = []

    for url in urls:
        print(f"Checking M3U8: {url}")

        status, detail, code, response_time, segment = check_m3u8(url)

        results.append([
            url,
            status,
            detail,
            code,
            f"{response_time:.3f}",
            segment
        ])

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "url",
            "status",
            "detail",
            "http_code",
            "response_time",
            "first_segment"
        ])

        writer.writerows(results)

    total = len(results)
    up = sum(1 for r in results if r[1] == "UP")
    down = total - up

    rate = (up / total * 100) if total else 0

    print()
    print("========================================")
    print("       TERMUX MEDIA HUB M3U8 CHECK")
    print("========================================")
    print(f"TOTAL URL    : {total}")
    print(f"UP           : {up}")
    print(f"DOWN         : {down}")
    print(f"SUCCESS RATE : {rate:.1f}%")
    print("========================================")
    print()

    for r in results:
        print(f"{r[1]:4} | {r[2]:24} | HTTP {r[3]} | {r[0]}")

    print()
    print(f"Report: {OUTPUT}")


if __name__ == "__main__":
    main()
