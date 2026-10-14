"""Summarise Claude Code session history: what I typed vs what Claude generated.

Reads ~/.claude/projects/<slug>/<session>.jsonl (stdlib only, no install needed).

    python claude_session_report.py                  # full report (keep on the work PC)
    python claude_session_report.py --stats-only     # no prompt text — safe to review for export
    python claude_session_report.py --since 2026-06-01
    python claude_session_report.py --root "D:/other/.claude/projects" --out report.md

--stats-only omits prompt bodies and file paths, leaving counts only. Even then,
check with your team lead before taking anything off a company machine.
"""
import argparse
import collections
import json
import os
import pathlib
import sys

TOOL_WRITE = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def sessions(root):
    for jf in sorted(pathlib.Path(root).glob("*/*.jsonl")):
        yield jf


def parse(jf):
    """Return (typed_prompts, tool_calls, files_touched, first_ts, last_ts, project)."""
    typed, tools, files = [], collections.Counter(), collections.Counter()
    first = last = None
    project = jf.parent.name
    for line in jf.open(encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = d.get("timestamp")
        if ts:
            first = min(first or ts, ts)
            last = max(last or ts, ts)
        t = d.get("type")
        msg = d.get("message") or {}
        if t == "user":
            c = msg.get("content")
            # A plain string means a human typed it. A list means tool_result etc.
            if isinstance(c, str) and c.strip():
                typed.append((ts, c.strip()))
        elif t == "assistant":
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    name = b.get("name", "?")
                    tools[name] += 1
                    if name in TOOL_WRITE:
                        fp = (b.get("input") or {}).get("file_path")
                        if fp:
                            files[fp] += 1
    return typed, tools, files, first, last, project


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(pathlib.Path.home() / ".claude" / "projects"))
    ap.add_argument("--since", help="ISO date, e.g. 2026-06-01")
    ap.add_argument("--stats-only", action="store_true")
    ap.add_argument("--out", default="claude_session_report.md")
    a = ap.parse_args()

    if not os.path.isdir(a.root):
        sys.exit(f"not found: {a.root}")

    rows, all_tools, all_files, all_typed = [], collections.Counter(), collections.Counter(), 0
    for jf in sessions(a.root):
        typed, tools, files, first, last, project = parse(jf)
        if a.since and (last or "") < a.since:
            continue
        if not typed and not tools:
            continue
        rows.append((jf, typed, tools, files, first, last, project))
        all_tools.update(tools)
        all_files.update(files)
        all_typed += len(typed)

    o = ["# Claude Code 세션 리포트", ""]
    o.append(f"- 세션 수: **{len(rows)}**")
    o.append(f"- 내가 직접 입력한 프롬프트: **{all_typed}건**")
    o.append(f"- Claude 도구 호출: **{sum(all_tools.values())}회**")
    if rows:
        o.append(f"- 기간: {min(r[4] or '' for r in rows)[:10]} ~ {max(r[5] or '' for r in rows)[:10]}")
    o += ["", "## 도구 사용 분포", "", "| 도구 | 횟수 |", "| --- | --- |"]
    for k, v in all_tools.most_common():
        o.append(f"| {k} | {v} |")

    if not a.stats_only:
        o += ["", "## 수정된 파일 (Edit/Write 대상)", "", "| 파일 | 수정 횟수 |", "| --- | --- |"]
        for k, v in all_files.most_common(80):
            o.append(f"| `{k}` | {v} |")
    else:
        o += ["", f"## 수정된 파일: 고유 **{len(all_files)}개** (경로 생략)"]

    o += ["", "## 세션별", ""]
    for jf, typed, tools, files, first, last, project in rows:
        o.append(f"### {(first or '?')[:16]} · {jf.stem[:8]} · `{project}`")
        o.append(f"- 내 프롬프트 {len(typed)}건 · 도구 호출 {sum(tools.values())}회 "
                 f"· 수정 파일 {len(files)}개")
        if not a.stats_only:
            o.append("")
            for ts, txt in typed:
                one = " ".join(txt.split())
                o.append(f"  - `{(ts or '')[11:16]}` {one[:300]}")
        o.append("")

    pathlib.Path(a.out).write_text("\n".join(o), encoding="utf-8")
    print(f"wrote {a.out}  ({len(rows)} sessions, {all_typed} typed prompts)")


if __name__ == "__main__":
    main()
