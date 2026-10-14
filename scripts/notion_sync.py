"""Create a Notion page under NOTION_PARENT_PAGE_ID.

Usage:
    python scripts/notion_sync.py "Title" "Body text, one paragraph per line"
"""
import json
import os
import sys
import urllib.request

NOTION_VERSION = "2022-06-28"


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


def create_page(token, parent_page_id, title, body):
    blocks = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": line}}]},
        }
        for line in body.splitlines()
        if line.strip()
    ]
    payload = {
        "parent": {"page_id": parent_page_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": blocks,
    }
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    env = load_env()
    token = env.get("NOTION_TOKEN")
    parent_id = env.get("NOTION_PARENT_PAGE_ID")
    if not token or not parent_id:
        print("Set NOTION_TOKEN and NOTION_PARENT_PAGE_ID in .env")
        sys.exit(1)
    title, body = sys.argv[1], sys.argv[2]
    result = create_page(token, parent_id, title, body)
    print("Created:", result.get("url", result))


if __name__ == "__main__":
    main()
