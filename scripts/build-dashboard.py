#!/usr/bin/env python3

import csv
import html
import os
from datetime import datetime, timezone

INPUT = "output/final-report.csv"
OUTPUT = "public/index.html"

os.makedirs("public", exist_ok=True)

rows = []

if os.path.exists(INPUT):
    with open(INPUT, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

total = len(rows)

counts = {}

for r in rows:
    status = r.get("classification", "UNVERIFIED")
    counts[status] = counts.get(status, 0) + 1

online = counts.get("ONLINE", 0)
dead = counts.get("DEAD", 0)
blocked = counts.get("BLOCKED", 0)
temporary = counts.get("TEMPORARY", 0)
unverified = counts.get("UNVERIFIED", 0)
invalid = counts.get("INVALID", 0)

rate = online / total * 100 if total else 0

generated = datetime.now(timezone.utc).strftime(
    "%Y-%m-%d %H:%M:%S UTC"
)


def badge(status):
    labels = {
        "ONLINE": ("ONLINE", "online"),
        "DEAD": ("DEAD", "dead"),
        "BLOCKED": ("BLOCKED", "blocked"),
        "TEMPORARY": ("TEMPORARY", "temporary"),
        "UNVERIFIED": ("UNVERIFIED", "unverified"),
        "INVALID": ("INVALID", "invalid"),
    }

    label, css = labels.get(
        status,
        ("UNKNOWN", "unverified")
    )

    return f'<span class="badge {css}">● {label}</span>'


cards = []

for r in rows:
    channel = html.escape(
        r.get("channel", "Unknown")
    )

    group = html.escape(
        r.get("group", "")
    )

    stream_type = html.escape(
        r.get("type", "")
    )

    url = html.escape(
        r.get("url", "")
    )

    classification = r.get(
        "classification",
        "UNVERIFIED"
    )

    detail = html.escape(
        r.get("final_detail", "")
    )

    http = html.escape(
        r.get("http_code", "")
    )

    response = html.escape(
        r.get("response_time", "")
    )

    segment = html.escape(
        r.get("segment_time", "")
    )

    cards.append(f"""
    <article class="channel {classification.lower()}">

      <div class="channel-head">

        <div>
          <div class="channel-name">{channel}</div>
          <div class="group">{group}</div>
        </div>

        {badge(classification)}

      </div>

      <div class="grid">

        <div>
          <small>TYPE</small>
          <strong>{stream_type}</strong>
        </div>

        <div>
          <small>HTTP</small>
          <strong>{http}</strong>
        </div>

        <div>
          <small>RESPONSE</small>
          <strong>{response}s</strong>
        </div>

        <div>
          <small>SEGMENT</small>
          <strong>{segment}s</strong>
        </div>

      </div>

      <div class="detail">
        {detail}
      </div>

      <details>
        <summary>Show URL</summary>
        <code>{url}</code>
      </details>

    </article>
    """)

channels = "\n".join(cards)

html_page = f"""<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<meta http-equiv="refresh"
      content="300">

<title>Termux Media Hub</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    background: #080b12;
    color: #f5f7ff;
    font-family:
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        sans-serif;
}}

.container {{
    width: min(1100px, 94%);
    margin: auto;
    padding: 28px 0 60px;
}}

header {{
    margin-bottom: 25px;
}}

h1 {{
    margin: 0;
    font-size: 30px;
}}

.subtitle {{
    color: #8d98ad;
    margin-top: 6px;
}}

.stats {{
    display: grid;
    grid-template-columns:
        repeat(6, 1fr);
    gap: 10px;
    margin: 25px 0;
}}

.stat {{
    background: #121824;
    border: 1px solid #252e40;
    border-radius: 14px;
    padding: 15px;
}}

.stat small {{
    color: #7f8ba2;
    font-size: 10px;
}}

.stat strong {{
    display: block;
    margin-top: 5px;
    font-size: 24px;
}}

.channel {{
    background: #111722;
    border: 1px solid #252e40;
    border-radius: 15px;
    padding: 18px;
    margin-bottom: 11px;
}}

.channel-head {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
}}

.channel-name {{
    font-weight: 700;
    font-size: 16px;
}}

.group {{
    color: #707c94;
    font-size: 11px;
    margin-top: 3px;
}}

.badge {{
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 11px;
    white-space: nowrap;
}}

.online {{
    border-color: #164c35;
}}

.dead {{
    border-color: #57222a;
}}

.blocked {{
    border-color: #5b4520;
}}

.temporary {{
    border-color: #59401d;
}}

.unverified {{
    border-color: #343d51;
}}

.invalid {{
    border-color: #54264d;
}}

.badge.online {{
    background: #103725;
    color: #4cffaa;
}}

.badge.dead {{
    background: #411b23;
    color: #ff6b7d;
}}

.badge.blocked {{
    background: #493915;
    color: #ffd66b;
}}

.badge.temporary {{
    background: #493315;
    color: #ffbd66;
}}

.badge.unverified {{
    background: #252d3d;
    color: #b6c0d4;
}}

.badge.invalid {{
    background: #42203c;
    color: #ff8be0;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(4, 1fr);
    gap: 8px;
    margin-top: 16px;
}}

.grid div {{
    background: #0b1019;
    border-radius: 9px;
    padding: 9px;
}}

.grid small {{
    display: block;
    color: #707c94;
    font-size: 9px;
}}

.grid strong {{
    display: block;
    margin-top: 3px;
}}

.detail {{
    color: #929db2;
    font-size: 12px;
    margin-top: 13px;
}}

details {{
    margin-top: 12px;
}}

summary {{
    cursor: pointer;
    color: #8390a8;
    font-size: 12px;
}}

code {{
    display: block;
    margin-top: 8px;
    padding: 10px;
    background: #080c13;
    border-radius: 8px;
    color: #aeb9cc;
    overflow-wrap: anywhere;
    font-size: 11px;
}}

footer {{
    color: #606b80;
    text-align: center;
    margin-top: 30px;
    font-size: 11px;
}}

@media(max-width:800px) {{

    .stats {{
        grid-template-columns:
            repeat(3, 1fr);
    }}

}}

@media(max-width:550px) {{

    .stats {{
        grid-template-columns:
            repeat(2, 1fr);
    }}

    .grid {{
        grid-template-columns:
            repeat(2, 1fr);
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

<div class="subtitle">
Playlist Intelligence Dashboard
</div>

</header>

<section class="stats">

<div class="stat">
<small>TOTAL</small>
<strong>{total}</strong>
</div>

<div class="stat">
<small>ONLINE</small>
<strong>{online}</strong>
</div>

<div class="stat">
<small>DEAD</small>
<strong>{dead}</strong>
</div>

<div class="stat">
<small>BLOCKED</small>
<strong>{blocked}</strong>
</div>

<div class="stat">
<small>UNVERIFIED</small>
<strong>{unverified}</strong>
</div>

<div class="stat">
<small>ONLINE RATE</small>
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

with open(
    OUTPUT,
    "w",
    encoding="utf-8"
) as f:
    f.write(html_page)

print("Dashboard created:", OUTPUT)
print("Total:", total)
print("Online:", online)
print("Dead:", dead)
print("Blocked:", blocked)
print("Unverified:", unverified)
print("Online rate:", f"{rate:.1f}%")
