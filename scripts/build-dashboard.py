#!/usr/bin/env python3

import csv
import html
import os
from datetime import datetime, timezone

INPUT = "output/m3u8-report.csv"
OUTPUT = "public/index.html"

os.makedirs("public", exist_ok=True)

rows = []

if os.path.exists(INPUT):
    with open(INPUT, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

total = len(rows)
up = sum(1 for r in rows if r["status"] == "UP")
down = total - up
rate = (up / total * 100) if total else 0

generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def status_badge(status):
    if status == "UP":
        return '<span class="badge up">● ONLINE</span>'
    return '<span class="badge down">● OFFLINE</span>'


cards = []

for r in rows:
    url = html.escape(r["url"])
    status = html.escape(r["status"])
    detail = html.escape(r["detail"])
    playlist_type = html.escape(r["playlist_type"])
    variants = html.escape(r["variants"])
    http_code = html.escape(r["http_code"])
    playlist_time = html.escape(r["playlist_time"])
    segment_time = html.escape(r["segment_time"])
    total_time = html.escape(r["total_time"])

    cards.append(f"""
    <article class="channel">
      <div class="channel-head">
        <div class="channel-name">{url}</div>
        {status_badge(status)}
      </div>

      <div class="grid">
        <div><small>TYPE</small><strong>{playlist_type}</strong></div>
        <div><small>VARIANTS</small><strong>{variants}</strong></div>
        <div><small>HTTP</small><strong>{http_code}</strong></div>
        <div><small>PLAYLIST</small><strong>{playlist_time}s</strong></div>
        <div><small>SEGMENT</small><strong>{segment_time}s</strong></div>
        <div><small>TOTAL</small><strong>{total_time}s</strong></div>
      </div>

      <div class="detail">{detail}</div>
    </article>
    """)

channels = "\n".join(cards)

html_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="300">
<title>Termux Media Hub</title>

<style>
* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  background: #0b1020;
  color: #f5f7ff;
  font-family: system-ui, -apple-system, sans-serif;
}}

.container {{
  width: min(1000px, 92%);
  margin: auto;
  padding: 30px 0 50px;
}}

header {{
  margin-bottom: 24px;
}}

h1 {{
  margin: 0;
  font-size: 30px;
}}

.subtitle {{
  color: #9da7bd;
  margin-top: 6px;
}}

.stats {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin: 24px 0;
}}

.stat, .channel {{
  background: #151c30;
  border: 1px solid #26304a;
  border-radius: 16px;
}}

.stat {{
  padding: 18px;
}}

.stat small {{
  display: block;
  color: #8f9ab3;
  font-size: 11px;
}}

.stat strong {{
  display: block;
  font-size: 26px;
  margin-top: 5px;
}}

.channel {{
  padding: 20px;
  margin-bottom: 14px;
}}

.channel-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
}}

.channel-name {{
  overflow-wrap: anywhere;
  font-weight: 700;
}}

.badge {{
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}}

.up {{
  background: #123b2a;
  color: #4cffaa;
}}

.down {{
  background: #401b24;
  color: #ff6b7d;
}}

.grid {{
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
  margin-top: 18px;
}}

.grid div {{
  background: #0e1527;
  border-radius: 10px;
  padding: 10px;
}}

.grid small {{
  display: block;
  color: #7f8aa5;
  font-size: 9px;
}}

.grid strong {{
  display: block;
  margin-top: 3px;
}}

.detail {{
  margin-top: 14px;
  color: #8f9ab3;
  font-size: 13px;
}}

footer {{
  color: #68738b;
  text-align: center;
  margin-top: 30px;
  font-size: 12px;
}}

@media (max-width: 700px) {{
  .stats {{
    grid-template-columns: repeat(2, 1fr);
  }}

  .grid {{
    grid-template-columns: repeat(3, 1fr);
  }}

  h1 {{
    font-size: 24px;
  }}
}}
</style>
</head>

<body>
<div class="container">

<header>
  <h1>📡 Termux Media Hub</h1>
  <div class="subtitle">M3U8 IPTV Intelligence Dashboard</div>
</header>

<section class="stats">
  <div class="stat">
    <small>TOTAL</small>
    <strong>{total}</strong>
  </div>

  <div class="stat">
    <small>ONLINE</small>
    <strong>{up}</strong>
  </div>

  <div class="stat">
    <small>OFFLINE</small>
    <strong>{down}</strong>
  </div>

  <div class="stat">
    <small>SUCCESS</small>
    <strong>{rate:.1f}%</strong>
  </div>
</section>

<section>
{channels}
</section>

<footer>
  Generated automatically · {generated}
</footer>

</div>
</body>
</html>
"""

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html_page)

print(f"Dashboard created: {OUTPUT}")
print(f"Channels: {total}")
print(f"Online: {up}")
print(f"Offline: {down}")
print(f"Success: {rate:.1f}%")
