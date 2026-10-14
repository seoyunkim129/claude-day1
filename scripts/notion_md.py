"""Markdown -> Notion blocks. Creates a rich page under NOTION_PARENT_PAGE_ID.

Usage:
    python scripts/notion_md.py "Page Title" path/to/doc.md [--icon 📊] [--parent PAGE_ID]

Supports: # ## ### headings, - bullets, 1. numbered, > quote, > :emoji: callout,
--- divider, ``` code fences (incl. mermaid), | markdown | tables |,
inline **bold** and `code`.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"
MAX_CHILDREN = 100
MAX_TEXT = 1900

# Notion accepts a fixed language enum for code blocks.
KNOWN_LANGS = {
    "mermaid", "sql", "python", "bash", "shell", "json", "yaml",
    "javascript", "typescript", "markdown", "plain text",
}


def load_env(path=".env"):
    env = dict(os.environ)
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip())
    return env


# ---------------------------------------------------------------- rich text

TOKEN = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def rich(text, color=None):
    """Split a line into Notion rich_text runs, honouring **bold** and `code`."""
    out = []
    for part in TOKEN.split(text):
        if not part:
            continue
        ann = {}
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, ann = part[2:-2], {"bold": True}
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            part, ann = part[1:-1], {"code": True}
        if color:
            ann["color"] = color
        while part:
            chunk, part = part[:MAX_TEXT], part[MAX_TEXT:]
            item = {"type": "text", "text": {"content": chunk}}
            if ann:
                item["annotations"] = dict(ann)
            out.append(item)
    return out or [{"type": "text", "text": {"content": ""}}]


def block(kind, **body):
    return {"object": "block", "type": kind, kind: body}


# ---------------------------------------------------------------- md -> blocks

CALLOUT = re.compile(r"^>\s*([\U0001F300-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF])\s*(.*)$")
HEADING = re.compile(r"^(#{1,3})\s+(.*)$")
BULLET = re.compile(r"^[-*]\s+(.*)$")
NUMBER = re.compile(r"^\d+\.\s+(.*)$")
TABLE_SEP = re.compile(r"^\|[\s:\-|]+\|$")


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def convert(md):
    lines = md.split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i].rstrip()

        # fenced code / mermaid
        if line.startswith("```"):
            lang = line[3:].strip().lower() or "plain text"
            if lang not in KNOWN_LANGS:
                lang = "plain text"
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            blocks.append(block("code", rich_text=rich("\n".join(buf)), language=lang))
            continue

        # table
        if line.startswith("|") and i + 1 < len(lines) and TABLE_SEP.match(lines[i + 1].strip()):
            header = split_row(line)
            width = len(header)
            rows = [header]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                cells = (cells + [""] * width)[:width]
                rows.append(cells)
                i += 1
            blocks.append(block(
                "table",
                table_width=width,
                has_column_header=True,
                has_row_header=False,
                children=[
                    {"object": "block", "type": "table_row",
                     "table_row": {"cells": [rich(c) for c in r]}}
                    for r in rows[:MAX_CHILDREN]
                ],
            ))
            continue

        if not line.strip():
            i += 1
            continue

        if line.strip() in ("---", "***", "___"):
            blocks.append(block("divider"))
            i += 1
            continue

        m = HEADING.match(line)
        if m:
            lvl = len(m.group(1))
            blocks.append(block(f"heading_{lvl}", rich_text=rich(m.group(2)),
                                is_toggleable=False))
            i += 1
            continue

        m = CALLOUT.match(line)
        if m:
            blocks.append(block("callout", rich_text=rich(m.group(2)),
                                icon={"type": "emoji", "emoji": m.group(1)},
                                color="gray_background"))
            i += 1
            continue

        if line.startswith(">"):
            blocks.append(block("quote", rich_text=rich(line[1:].strip())))
            i += 1
            continue

        m = BULLET.match(line)
        if m:
            blocks.append(block("bulleted_list_item", rich_text=rich(m.group(1))))
            i += 1
            continue

        m = NUMBER.match(line)
        if m:
            blocks.append(block("numbered_list_item", rich_text=rich(m.group(1))))
            i += 1
            continue

        blocks.append(block("paragraph", rich_text=rich(line.strip())))
        i += 1
    return blocks


# ---------------------------------------------------------------- api

def call(token, method, path, payload=None):
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(payload).encode("utf-8") if payload else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{e.code} {e.reason}\n{e.read().decode('utf-8')[:900]}")


def replace_page(token, page_id, blocks):
    """Archive every existing child block, then re-append. Keeps the same URL."""
    cur, old = None, []
    while True:
        q = f"?page_size=100" + (f"&start_cursor={cur}" if cur else "")
        d = call(token, "GET", f"/blocks/{page_id}/children{q}")
        old += [b["id"] for b in d["results"]]
        if not d.get("has_more"):
            break
        cur = d["next_cursor"]
    for bid in old:
        call(token, "PATCH", f"/blocks/{bid}", {"archived": True})
    rest = blocks
    while rest:
        call(token, "PATCH", f"/blocks/{page_id}/children",
             {"children": rest[:MAX_CHILDREN]})
        rest = rest[MAX_CHILDREN:]
        time.sleep(0.35)
    return call(token, "GET", f"/pages/{page_id}")


def publish(token, parent, title, blocks, icon=None):
    payload = {
        "parent": {"page_id": parent},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": blocks[:MAX_CHILDREN],
    }
    if icon:
        payload["icon"] = {"type": "emoji", "emoji": icon}
    page = call(token, "POST", "/pages", payload)
    pid = page["id"]
    rest = blocks[MAX_CHILDREN:]
    while rest:
        call(token, "PATCH", f"/blocks/{pid}/children",
             {"children": rest[:MAX_CHILDREN]})
        rest = rest[MAX_CHILDREN:]
        time.sleep(0.35)
    return page


def main():
    args = [a for a in sys.argv[1:]]
    icon = parent_override = None
    if "--icon" in args:
        k = args.index("--icon")
        icon = args[k + 1]
        del args[k:k + 2]
    if "--parent" in args:
        k = args.index("--parent")
        parent_override = args[k + 1]
        del args[k:k + 2]
    update_id = None
    if "--update" in args:
        k = args.index("--update")
        update_id = args[k + 1]
        del args[k:k + 2]
    if update_id:
        env = load_env()
        blocks = convert(open(args[-1], encoding="utf-8").read())
        page = replace_page(env["NOTION_TOKEN"], update_id, blocks)
        print(f"blocks: {len(blocks)}")
        print("Updated:", page.get("url"))
        return
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)

    title, path = args[0], args[1]
    env = load_env()
    token = env.get("NOTION_TOKEN")
    parent = parent_override or env.get("NOTION_PARENT_PAGE_ID")
    if not token or not parent:
        sys.exit("Set NOTION_TOKEN and NOTION_PARENT_PAGE_ID in .env")

    blocks = convert(open(path, encoding="utf-8").read())
    page = publish(token, parent, title, blocks, icon)
    print(f"blocks: {len(blocks)}")
    print("Created:", page.get("url"))


if __name__ == "__main__":
    main()
