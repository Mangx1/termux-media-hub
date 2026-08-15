#!/usr/bin/env python3

import csv
import os

BASE = "output/playlist-report.csv"
RETRY = "output/retry-report.csv"

FINAL = "output/final-report.csv"
SUMMARY = "output/final-summary.txt"


def load_csv(path):
    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    base = load_csv(BASE)
    retry = load_csv(RETRY)

    if not base:
        print(f"ERROR: {BASE} tidak ditemukan atau kosong")
        return 1

    retry_map = {
        row["url"]: row
        for row in retry
        if row.get("url")
    }

    final = []

    for row in base:
        url = row["url"]
        original_status = row.get("status", "")
        original_detail = row.get("detail", "")

        # Default: pertahankan hasil scanner utama.
        status = original_status
        detail = original_detail
        classification = "UNVERIFIED"

        if original_status == "ONLINE":
            classification = "ONLINE"

        elif original_status == "INVALID":
            classification = "INVALID"

        elif url in retry_map:
            r = retry_map[url]
            retry_status = r.get("retry_status", "")

            if retry_status == "ONLINE":
                classification = "ONLINE"
                status = "ONLINE"
                detail = "RETRY_CONFIRMED"

            elif retry_status == "DEAD":
                classification = "DEAD"
                status = "ERROR"
                detail = "HTTP_404_CONFIRMED"

            elif retry_status == "BLOCKED":
                classification = "BLOCKED"
                status = "ERROR"
                detail = "HTTP_403_BLOCKED"

            elif retry_status == "TEMPORARY":
                classification = "TEMPORARY"
                status = "ERROR"
                detail = "HTTP_503_TEMPORARY"

            elif retry_status == "CONNECTION":
                classification = "UNVERIFIED"
                status = "ERROR"
                detail = "CONNECTION_UNVERIFIED"

            else:
                classification = "UNVERIFIED"

        else:
            classification = "UNVERIFIED"

        result = dict(row)

        result["classification"] = classification
        result["final_status"] = status
        result["final_detail"] = detail

        final.append(result)

    fields = [
        "channel",
        "tvg_id",
        "group",
        "type",
        "url",
        "status",
        "detail",
        "classification",
        "final_status",
        "final_detail",
        "http_code",
        "response_time",
        "segment_time",
        "bytes",
        "headers",
    ]

    os.makedirs("output", exist_ok=True)

    with open(
        FINAL,
        "w",
        encoding="utf-8",
        newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fields,
            extrasaction="ignore"
        )

        writer.writeheader()

        for row in final:
            writer.writerow(row)

    counts = {}

    for row in final:
        c = row["classification"]
        counts[c] = counts.get(c, 0) + 1

    total = len(final)
    online = counts.get("ONLINE", 0)
    dead = counts.get("DEAD", 0)
    blocked = counts.get("BLOCKED", 0)
    temporary = counts.get("TEMPORARY", 0)
    unverified = counts.get("UNVERIFIED", 0)
    invalid = counts.get("INVALID", 0)

    verified_rate = (
        online / total * 100
        if total else 0
    )

    with open(
        SUMMARY,
        "w",
        encoding="utf-8"
    ) as f:
        f.write("TERMUX MEDIA HUB\n")
        f.write("==============================\n")
        f.write("FINAL PLAYLIST REPORT\n")
        f.write("==============================\n")
        f.write(f"TOTAL       : {total}\n")
        f.write(f"ONLINE      : {online}\n")
        f.write(f"DEAD        : {dead}\n")
        f.write(f"BLOCKED     : {blocked}\n")
        f.write(f"TEMPORARY   : {temporary}\n")
        f.write(f"UNVERIFIED  : {unverified}\n")
        f.write(f"INVALID     : {invalid}\n")
        f.write(f"ONLINE RATE : {verified_rate:.1f}%\n")
        f.write("==============================\n")

    print()
    print("========================================")
    print("       TERMUX MEDIA HUB")
    print("       FINAL PLAYLIST REPORT")
    print("========================================")
    print(f"TOTAL       : {total}")
    print(f"ONLINE      : {online}")
    print(f"DEAD        : {dead}")
    print(f"BLOCKED     : {blocked}")
    print(f"TEMPORARY   : {temporary}")
    print(f"UNVERIFIED  : {unverified}")
    print(f"INVALID     : {invalid}")
    print(f"ONLINE RATE : {verified_rate:.1f}%")
    print("========================================")
    print()
    print(f"CSV     : {FINAL}")
    print(f"SUMMARY : {SUMMARY}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
