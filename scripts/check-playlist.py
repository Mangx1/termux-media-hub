#!/usr/bin/env python3

import csv
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

TIMEOUT = 15
WORKERS = 12
OUTPUT = "output/playlist-report.csv"


def curl_request(url, headers=None, download_body=True):
    start = time.time()

    args = [
        "curl",
        "-L",
        "-sS",
        "--max-time", str(TIMEOUT),
        "-A", "Mozilla/5.0",
        "--connect-timeout", "8",
        "-w",
        "\n__TMH_META__%{http_code}|%{url_effective}|%{size_download}|%{content_type}|%{time_starttransfer}",
    ]

    if not download_body:
        args += ["-o", "/dev/null"]

    if headers:
        for key, value in headers.items():
            args += ["-H", f"{key}: {value}"]

    args.append(url)

    try:
        p = subprocess.run(
            args,
            capture_output=True,
            text=False
        )
    except Exception as e:
        return {
            "body": b"",
            "code": 0,
            "final_url": url,
            "elapsed": time.time() - start,
            "bytes": 0,
            "content_type": "",
            "start_transfer": 0,
            "error": str(e),
            "curl_exit": -1,
            "timed_out": False,
        }

    elapsed = time.time() - start

    marker = b"\n__TMH_META__"

    if marker not in p.stdout:
        error = p.stderr.decode("utf-8", errors="replace").strip()

        return {
            "body": p.stdout if download_body else b"",
            "code": 0,
            "final_url": url,
            "elapsed": elapsed,
            "bytes": len(p.stdout),
            "content_type": "",
            "start_transfer": 0,
            "error": error or "No HTTP metadata",
            "curl_exit": p.returncode,
            "timed_out": p.returncode == 28,
        }

    body, meta = p.stdout.rsplit(marker, 1)

    try:
        parts = meta.decode("utf-8", errors="replace").strip().split("|", 4)

        code = int(parts[0])
        final_url = parts[1]
        size = float(parts[2] or 0)
        content_type = parts[3]
        start_transfer = float(parts[4] or 0)

    except Exception:
        return {
            "body": body if download_body else b"",
            "code": 0,
            "final_url": url,
            "elapsed": elapsed,
            "bytes": len(body),
            "content_type": "",
            "start_transfer": 0,
            "error": "Invalid HTTP metadata",
            "curl_exit": p.returncode,
            "timed_out": p.returncode == 28,
        }

    stderr = p.stderr.decode("utf-8", errors="replace").strip()

    return {
        "body": body if download_body else b"",
        "code": code,
        "final_url": final_url,
        "elapsed": elapsed,
        "bytes": int(size),
        "content_type": content_type,
        "start_transfer": start_transfer,
        "error": stderr,
        "curl_exit": p.returncode,
        "timed_out": p.returncode == 28,
    }


def decode_body(data):
    return data.decode("utf-8", errors="replace")


def parse_playlist(text, base_url):
    entries = []

    current = None

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            continue

        if line.startswith("#EXTINF:"):
            comma = line.find(",")

            info = line if comma < 0 else line[:comma]
            name = "Unknown" if comma < 0 else line[comma + 1:].strip()

            tvg_id = ""
            group = ""

            m = re.search(r'tvg-id="([^"]*)"', info)
            if m:
                tvg_id = m.group(1)

            m = re.search(r'group-title="([^"]*)"', info)
            if m:
                group = m.group(1)

            current = {
                "channel": name or "Unknown",
                "tvg_id": tvg_id,
                "group": group,
                "headers": {},
            }

            continue

        if current is not None and line.startswith("#EXTVLCOPT:"):
            option = line[len("#EXTVLCOPT:"):]

            if option.startswith("http-user-agent="):
                current["headers"]["User-Agent"] = option.split("=", 1)[1]

            elif option.startswith("http-referrer="):
                current["headers"]["Referer"] = option.split("=", 1)[1]

            elif option.startswith("http-referer="):
                current["headers"]["Referer"] = option.split("=", 1)[1]

            continue

        if line.startswith("#"):
            continue

        if current is None:
            current = {
                "channel": "Unknown",
                "tvg_id": "",
                "group": "",
                "headers": {},
            }

        entries.append({
            "channel": current["channel"],
            "tvg_id": current["tvg_id"],
            "group": current["group"],
            "url": urljoin(base_url, line),
            "headers": dict(current["headers"]),
        })

        current = None

    return entries


def classify_url(url, content_type=""):
    u = url.lower()
    ct = content_type.lower()

    if ".mpd" in u or "dash" in ct:
        return "MPD"

    if ".m3u8" in u or "mpegurl" in ct or "x-mpegurl" in ct:
        return "M3U8"

    if ".mp3" in u or ".aac" in u or ".aacp" in u:
        return "RADIO"

    if "audio/" in ct:
        return "RADIO"

    if "video/" in ct:
        return "LIVE"

    return "STREAM"


def check_m3u8(url, headers):
    r = curl_request(url, headers, True)

    # A normal HTTP failure.
    if r["code"] >= 400:
        return result(
            "ERROR",
            "HTTP_ERROR",
            "M3U8",
            r
        )

    # Connection failure before any HTTP response.
    if r["code"] == 0:
        return result(
            "ERROR",
            "CONNECTION_ERROR",
            "M3U8",
            r
        )

    body = decode_body(r["body"])

    if "#EXTM3U" not in body[:5000]:
        return result(
            "INVALID",
            "NOT_M3U8",
            "M3U8",
            r
        )

    # Master playlist.
    if "#EXT-X-STREAM-INF" in body:
        variant = None
        lines = body.splitlines()

        for i, line in enumerate(lines):
            if line.strip().startswith("#EXT-X-STREAM-INF"):
                for candidate in lines[i + 1:]:
                    candidate = candidate.strip()

                    if candidate and not candidate.startswith("#"):
                        variant = candidate
                        break

            if variant:
                break

        if variant:
            variant_url = urljoin(r["final_url"], variant)

            vr = curl_request(
                variant_url,
                headers,
                True
            )

            if vr["code"] >= 400:
                return result(
                    "ERROR",
                    "VARIANT_HTTP_ERROR",
                    "M3U8",
                    r,
                    extra_time=vr["elapsed"]
                )

            if vr["code"] == 0:
                return result(
                    "ERROR",
                    "VARIANT_CONNECTION_ERROR",
                    "M3U8",
                    r,
                    extra_time=vr["elapsed"]
                )

            vbody = decode_body(vr["body"])

            if "#EXTM3U" not in vbody[:5000]:
                return result(
                    "INVALID",
                    "INVALID_VARIANT",
                    "M3U8",
                    r,
                    extra_time=vr["elapsed"]
                )

            body = vbody
            r["elapsed"] += vr["elapsed"]
            r["final_url"] = vr["final_url"]

    segment = None

    for line in body.splitlines():
        line = line.strip()

        if line and not line.startswith("#"):
            segment = line
            break

    if not segment:
        return result(
            "ERROR",
            "NO_SEGMENT",
            "M3U8",
            r
        )

    segment_url = urljoin(r["final_url"], segment)

    sr = curl_request(
        segment_url,
        headers,
        False
    )

    if 200 <= sr["code"] < 400:
        return {
            "status": "ONLINE",
            "detail": "M3U8_OK_SEGMENT_OK",
            "type": "M3U8",
            "http_code": sr["code"],
            "response_time": r["elapsed"],
            "segment_time": sr["elapsed"],
            "bytes": r["bytes"],
            "headers": "YES" if headers else "NO",
        }

    return {
        "status": "ERROR",
        "detail": "SEGMENT_ERROR",
        "type": "M3U8",
        "http_code": sr["code"],
        "response_time": r["elapsed"],
        "segment_time": sr["elapsed"],
        "bytes": r["bytes"],
        "headers": "YES" if headers else "NO",
    }


def check_mpd(url, headers):
    r = curl_request(url, headers, True)

    if r["code"] >= 400:
        return result(
            "ERROR",
            "HTTP_ERROR",
            "MPD",
            r
        )

    if r["code"] == 0:
        return result(
            "ERROR",
            "CONNECTION_ERROR",
            "MPD",
            r
        )

    body = decode_body(r["body"])

    if "<MPD" not in body[:10000]:
        return result(
            "INVALID",
            "NOT_MPD",
            "MPD",
            r
        )

    return result(
        "ONLINE",
        "MPD_OK",
        "MPD",
        r
    )


def check_radio(url, headers):
    r = curl_request(
        url,
        headers,
        False
    )

    # Important:
    # curl exit 28 means max-time was reached.
    # For a live radio stream this can be SUCCESS if
    # the server actually returned HTTP data.
    if r["code"] >= 200 and r["code"] < 400:

        if r["timed_out"] and r["bytes"] > 0:
            return {
                "status": "ONLINE",
                "detail": "LIVE_STREAM_DATA_RECEIVED",
                "type": "RADIO",
                "http_code": r["code"],
                "response_time": r["elapsed"],
                "segment_time": 0,
                "bytes": r["bytes"],
                "headers": "YES" if headers else "NO",
            }

        return {
            "status": "ONLINE",
            "detail": "LIVE_STREAM_OK",
            "type": "RADIO",
            "http_code": r["code"],
            "response_time": r["elapsed"],
            "segment_time": 0,
            "bytes": r["bytes"],
            "headers": "YES" if headers else "NO",
        }

    if r["code"] >= 400:
        return result(
            "ERROR",
            "HTTP_ERROR",
            "RADIO",
            r
        )

    return result(
        "ERROR",
        "CONNECTION_ERROR",
        "RADIO",
        r
    )


def result(status, detail, stream_type, r, extra_time=0):
    return {
        "status": status,
        "detail": detail,
        "type": stream_type,
        "http_code": r["code"],
        "response_time": r["elapsed"] + extra_time,
        "segment_time": 0,
        "bytes": r["bytes"],
        "headers": "",
    }


def check_entry(entry):
    url = entry["url"]
    headers = entry["headers"]

    # First request lets us discover content type for ambiguous URLs.
    probe = curl_request(
        url,
        headers,
        True
    )

    if probe["code"] == 0:
        # It may be a live radio/audio stream that never terminates.
        # Try classifying by URL before declaring it dead.
        stream_type = classify_url(url)

        if stream_type == "RADIO":
            r = check_radio(url, headers)
        else:
            r = result(
                "ERROR",
                "CONNECTION_ERROR",
                stream_type,
                probe
            )

    elif probe["code"] >= 400:
        stream_type = classify_url(
            url,
            probe["content_type"]
        )

        r = result(
            "ERROR",
            "HTTP_ERROR",
            stream_type,
            probe
        )

    else:
        stream_type = classify_url(
            probe["final_url"],
            probe["content_type"]
        )

        # We already downloaded the response, so avoid another
        # full request for normal M3U8/MPD.
        body = decode_body(probe["body"])

        if stream_type == "M3U8" or "#EXTM3U" in body[:5000]:
            r = check_m3u8(url, headers)

        elif stream_type == "MPD" or "<MPD" in body[:10000]:
            r = check_mpd(url, headers)

        elif stream_type == "RADIO":
            # Probe got an HTTP response, therefore the live stream
            # is reachable.
            r = {
                "status": "ONLINE",
                "detail": "LIVE_AUDIO_REACHABLE",
                "type": "RADIO",
                "http_code": probe["code"],
                "response_time": probe["elapsed"],
                "segment_time": 0,
                "bytes": probe["bytes"],
                "headers": "YES" if headers else "NO",
            }

        else:
            r = {
                "status": "ONLINE",
                "detail": "HTTP_STREAM_REACHABLE",
                "type": stream_type,
                "http_code": probe["code"],
                "response_time": probe["elapsed"],
                "segment_time": 0,
                "bytes": probe["bytes"],
                "headers": "YES" if headers else "NO",
            }

    r.update({
        "channel": entry["channel"],
        "tvg_id": entry["tvg_id"],
        "group": entry["group"],
        "url": url,
    })

    return r


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("python scripts/check-playlist.py <PLAYLIST_URL>")
        sys.exit(1)

    playlist_url = sys.argv[1]

    print("========================================")
    print("       TERMUX MEDIA HUB")
    print("       PLAYLIST INTELLIGENCE")
    print("========================================")
    print()
    print("Downloading playlist...")
    print(playlist_url)
    print()

    r = curl_request(
        playlist_url,
        None,
        True
    )

    if r["code"] < 200 or r["code"] >= 400:
        print(f"Playlist download failed: HTTP {r['code']}")
        print(r["error"])
        sys.exit(1)

    text = decode_body(r["body"])

    if "#EXTM3U" not in text[:5000]:
        print("ERROR: Playlist does not contain #EXTM3U")
        sys.exit(1)

    entries = parse_playlist(
        text,
        r["final_url"]
    )

    print(f"Entries found : {len(entries)}")
    print(f"Workers       : {WORKERS}")
    print()

    results = [None] * len(entries)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:

        futures = {
            executor.submit(check_entry, entry): i
            for i, entry in enumerate(entries)
        }

        completed = 0

        for future in as_completed(futures):
            index = futures[future]

            try:
                results[index] = future.result()

            except Exception as e:
                entry = entries[index]

                results[index] = {
                    "channel": entry["channel"],
                    "tvg_id": entry["tvg_id"],
                    "group": entry["group"],
                    "url": entry["url"],
                    "status": "ERROR",
                    "detail": type(e).__name__,
                    "type": "UNKNOWN",
                    "http_code": 0,
                    "response_time": 0,
                    "segment_time": 0,
                    "bytes": 0,
                    "headers": "NO",
                }

            completed += 1

            x = results[index]

            print(
                f"[{completed:3}/{len(entries)}] "
                f"{x['status']:7} "
                f"{x['type']:6} "
                f"{x['channel'][:40]}"
            )

    os.makedirs("output", exist_ok=True)

    with open(
        OUTPUT,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        fields = [
            "channel",
            "tvg_id",
            "group",
            "type",
            "url",
            "status",
            "detail",
            "http_code",
            "response_time",
            "segment_time",
            "bytes",
            "headers",
        ]

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        for x in results:
            x["response_time"] = f'{x["response_time"]:.3f}'
            x["segment_time"] = f'{x["segment_time"]:.3f}'
            writer.writerow({
                field: x.get(field, "")
                for field in fields
            })

    total = len(results)

    online = sum(
        x["status"] == "ONLINE"
        for x in results
    )

    errors = sum(
        x["status"] == "ERROR"
        for x in results
    )

    invalid = sum(
        x["status"] == "INVALID"
        for x in results
    )

    rate = online / total * 100 if total else 0

    print()
    print("========================================")
    print("          SCAN COMPLETE")
    print("========================================")
    print(f"TOTAL    : {total}")
    print(f"ONLINE   : {online}")
    print(f"ERROR    : {errors}")
    print(f"INVALID  : {invalid}")
    print(f"SUCCESS  : {rate:.1f}%")
    print("========================================")
    print()
    print(f"Report: {OUTPUT}")


if __name__ == "__main__":
    main()
