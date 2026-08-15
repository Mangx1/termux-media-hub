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
        "curl", "-L", "-sS",
        "--max-time", str(TIMEOUT),
        "-A", "Mozilla/5.0",
        "-w", "\n__HTTP__%{http_code}|%{url_effective}",
    ]

    if not text_body:
        args += ["-o", "/dev/null"]

    args.append(url)

    result = subprocess.run(args, capture_output=True, text=False)
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


def first_media_segment(body):
    for line in body.splitlines():
        line = line.strip()

        if line and not line.startswith("#"):
            return line

    return None


def check_m3u8(url):
    body, code, final_url, playlist_time, error = curl_get(url)

    if body is None:
        return {
            "status": "DOWN",
            "detail": "CURL_ERROR",
            "playlist_type": "UNKNOWN",
            "variants": 0,
            "http_code": code,
            "playlist_time": playlist_time,
            "segment_time": 0,
            "total_time": playlist_time,
            "segment": error,
        }

    if code < 200 or code >= 400:
        return {
            "status": "DOWN",
            "detail": "HTTP_ERROR",
            "playlist_type": "UNKNOWN",
            "variants": 0,
            "http_code": code,
            "playlist_time": playlist_time,
            "segment_time": 0,
            "total_time": playlist_time,
            "segment": "",
        }

    if "#EXTM3U" not in body[:2000]:
        return {
            "status": "DOWN",
            "detail": "NOT_M3U8",
            "playlist_type": "UNKNOWN",
            "variants": 0,
            "http_code": code,
            "playlist_time": playlist_time,
            "segment_time": 0,
            "total_time": playlist_time,
            "segment": "",
        }

    lines = [x.strip() for x in body.splitlines() if x.strip()]

    variants = []
    for i, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            for candidate in lines[i + 1:]:
                if not candidate.startswith("#"):
                    variants.append(candidate)
                    break

    if variants:
        playlist_type = "MASTER"
        variant_url = urljoin(final_url, variants[0])

        vbody, vcode, vfinal, variant_time, verr = curl_get(variant_url)

        if vbody is None:
            return {
                "status": "DOWN",
                "detail": "VARIANT_ERROR",
                "playlist_type": playlist_type,
                "variants": len(variants),
                "http_code": vcode,
                "playlist_time": playlist_time,
                "segment_time": 0,
                "total_time": playlist_time + variant_time,
                "segment": verr,
            }

        if vcode < 200 or vcode >= 400:
            return {
                "status": "DOWN",
                "detail": "VARIANT_HTTP_ERROR",
                "playlist_type": playlist_type,
                "variants": len(variants),
                "http_code": vcode,
                "playlist_time": playlist_time,
                "segment_time": 0,
                "total_time": playlist_time + variant_time,
                "segment": variant_url,
            }

        if "#EXTM3U" not in vbody[:2000]:
            return {
                "status": "DOWN",
                "detail": "INVALID_VARIANT",
                "playlist_type": playlist_type,
                "variants": len(variants),
                "http_code": vcode,
                "playlist_time": playlist_time,
                "segment_time": 0,
                "total_time": playlist_time + variant_time,
                "segment": variant_url,
            }

        body = vbody
        final_url = vfinal
        playlist_time += variant_time
    else:
        playlist_type = "MEDIA"

    segment = first_media_segment(body)

    if not segment:
        return {
            "status": "DOWN",
            "detail": "NO_SEGMENT",
            "playlist_type": playlist_type,
            "variants": len(variants),
            "http_code": code,
            "playlist_time": playlist_time,
            "segment_time": 0,
            "total_time": playlist_time,
            "segment": "",
        }

    segment_url = urljoin(final_url, segment)

    _, scode, _, segment_time, _ = curl_get(
        segment_url,
        text_body=False
    )

    total_time = playlist_time + segment_time

    if 200 <= scode < 400:
        return {
            "status": "UP",
            "detail": "PLAYLIST_OK_SEGMENT_OK",
            "playlist_type": playlist_type,
            "variants": len(variants),
            "http_code": scode,
            "playlist_time": playlist_time,
            "segment_time": segment_time,
            "total_time": total_time,
            "segment": segment_url,
        }

    return {
        "status": "DOWN",
        "detail": "SEGMENT_ERROR",
        "playlist_type": playlist_type,
        "variants": len(variants),
        "http_code": scode,
        "playlist_time": playlist_time,
        "segment_time": segment_time,
        "total_time": total_time,
        "segment": segment_url,
    }


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

        result = check_m3u8(url)
        results.append((url, result))

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "url",
            "status",
            "detail",
            "playlist_type",
            "variants",
            "http_code",
            "playlist_time",
            "segment_time",
            "total_time",
            "first_segment"
        ])

        for url, r in results:
            writer.writerow([
                url,
                r["status"],
                r["detail"],
                r["playlist_type"],
                r["variants"],
                r["http_code"],
                f'{r["playlist_time"]:.3f}',
                f'{r["segment_time"]:.3f}',
                f'{r["total_time"]:.3f}',
                r["segment"]
            ])

    total = len(results)
    up = sum(1 for _, r in results if r["status"] == "UP")
    down = total - up
    rate = (up / total * 100) if total else 0

    print()
    print("========================================")
    print("      TERMUX MEDIA HUB INTELLIGENCE")
    print("========================================")
    print(f"TOTAL URL    : {total}")
    print(f"UP           : {up}")
    print(f"DOWN         : {down}")
    print(f"SUCCESS RATE : {rate:.1f}%")
    print("========================================")
    print()

    for url, r in results:
        print(f"URL      : {url}")
        print(f"STATUS   : {r['status']}")
        print(f"TYPE     : {r['playlist_type']}")
        print(f"VARIANTS : {r['variants']}")
        print(f"DETAIL   : {r['detail']}")
        print(f"HTTP     : {r['http_code']}")
        print(f"PLAYLIST : {r['playlist_time']:.3f}s")
        print(f"SEGMENT  : {r['segment_time']:.3f}s")
        print(f"TOTAL    : {r['total_time']:.3f}s")
        print("----------------------------------------")

    print(f"Report: {OUTPUT}")


if __name__ == "__main__":
    main()
