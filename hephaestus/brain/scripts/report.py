#!/usr/bin/env python3
"""Vault graph report. Never fails; reporting only. The gate is lint.py.

Prints page count, link density, orphans by inbound links, and the top hubs.
Density is the number worth watching: notes grow linearly, usefulness grows with
links. See '20 Notes/Following links outward is multi-hop retrieval'.
"""
import collections
import os
import re
import sys

VAULT = os.environ.get("OBSIDIAN_VAULT_PATH") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
DIRS = ["10 Sources", "20 Notes", "30 Projects", "90 Meta"]
WIKILINK = re.compile(r"\[\[([^\]|#]+)")

pages = {}
for d in DIRS:
    root = os.path.join(VAULT, d)
    if not os.path.isdir(root):
        continue
    for f in sorted(os.listdir(root)):
        if f.endswith(".md"):
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                pages[f[:-3]] = (d, fh.read())

if not pages:
    print("no pages found")
    sys.exit(0)

outbound = collections.Counter()
inbound = collections.Counter({t: 0 for t in pages})
broken = []
edges = 0
for title, (d, body) in pages.items():
    for link in sorted({x.strip() for x in WIKILINK.findall(body)}):
        if link == title:
            continue
        outbound[title] += 1
        edges += 1
        if link in inbound:
            inbound[link] += 1
        else:
            broken.append((title, link))

print(f"vault:   {VAULT}")
print(f"pages:   {len(pages)}")
print(f"edges:   {edges}")
print(f"density: {edges / len(pages):.1f} outbound links per page")
print()

orphans = [t for t, c in inbound.items() if c == 0]
print(f"unreachable (0 inbound links): {len(orphans)}")
for t in sorted(orphans):
    print(f"  {t}")
print()

if broken:
    print(f"links to nonexistent pages: {len(broken)}")
    for src, link in broken:
        print(f"  {src} -> {link}")
    print()

print("top hubs by inbound links:")
for t, c in inbound.most_common(8):
    print(f"  {c:>3}  {t}")
