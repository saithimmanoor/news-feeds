#!/usr/bin/env python3
"""Collect headlines + links from public RSS/Atom feeds into headlines.json.
Standard library only. A failing feed never stops the run; its status is recorded."""
import json, sys, time, datetime as dt
import urllib.request, urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

MAX_PER_FEED = 8
MAX_AGE_HOURS = 72
UA = "Mozilla/5.0 (compatible; PersonalNewsDesk/1.0; personal RSS reader)"

def local(tag):
    return tag.rsplit('}', 1)[-1]

def child_text(el, name):
    for c in el:
        if local(c.tag) == name and (c.text or '').strip():
            return c.text.strip()
    return ''

def atom_link(el):
    for c in el:
        if local(c.tag) == 'link':
            if c.get('href') and c.get('rel', 'alternate') == 'alternate':
                return c.get('href').strip()
    return ''

def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)

def parse_feed(data):
    root = ET.fromstring(data)
    items = []
    for el in root.iter():
        if local(el.tag) not in ('item', 'entry'):
            continue
        title = child_text(el, 'title')
        link = child_text(el, 'link') or atom_link(el) or child_text(el, 'guid')
        date = parse_date(child_text(el, 'pubDate') or child_text(el, 'published')
                          or child_text(el, 'updated') or child_text(el, 'date'))
        if title and link.startswith('http'):
            items.append((title, link, date))
    return items

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

def main(cfg_path, out_path):
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=MAX_AGE_HOURS)
    out_items, status, seen = [], [], set()
    for f in cfg['feeds']:
        entry = {"name": f['name'], "topic": f['topic'], "url": f['url']}
        try:
            items = parse_feed(fetch(f['url']))
            kept = 0
            for title, link, date in items:
                if link in seen:
                    continue
                if date and date < cutoff:
                    continue
                seen.add(link)
                out_items.append({"source": f['name'], "topic": f['topic'], "title": title,
                                  "url": link, "date": date.isoformat() if date else ""})
                kept += 1
                if kept >= MAX_PER_FEED:
                    break
            entry.update(ok=True, items=kept)
        except Exception as e:
            entry.update(ok=False, items=0, error=f"{type(e).__name__}: {e}"[:200])
        status.append(entry)
        time.sleep(0.5)
    out_items.sort(key=lambda i: i['date'], reverse=True)
    json.dump({"generated_utc": now.isoformat(timespec='seconds'), "status": status, "items": out_items},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ok = sum(1 for s in status if s['ok'])
    print(f"{ok}/{len(status)} feeds ok, {len(out_items)} items")
    for s in status:
        print(("OK   " if s['ok'] else "FAIL ") + s['name'] + " [" + s['topic'] + "] " + str(s['items']) + " " + s.get('error', ''))

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'feeds.json',
         sys.argv[2] if len(sys.argv) > 2 else 'headlines.json')
