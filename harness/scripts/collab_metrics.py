"""AI 협업 지표 수집기 — 모든 프로젝트의 Claude Code 세션과 기록 문서를 모아 숫자로 만든다.

읽는 곳 (stdlib만 사용, 설치 불필요):
  1) ~/.claude/projects/*/*.jsonl          세션 원본 (프롬프트·도구 호출)
  2) <프로젝트>/docs/포트폴리오-기록.md     결정(D)·검증(V)·AI오류(M)·프롬프트(P) 기록
  3) <프로젝트>/docs/작업기록.md            날짜별 작업 항목

    python collab_metrics.py                          # ~/.claude/collab-harness/metrics.json + report.md
    python collab_metrics.py --since 2026-09-01
    python collab_metrics.py --html docs/dashboard.html

프롬프트 원문·파일 경로는 출력하지 않는다. 숫자와 프로젝트 이름만 남긴다.
'교정'·'되묻기'는 키워드 휴리스틱이라 근사값이다 (report에 그렇게 표시한다).
"""
import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys

HOME = pathlib.Path.home()
ROOT = HOME / ".claude" / "projects"
# 결과·캐시는 레포 밖에 둔다 (label.csv 에 프롬프트 원문이 들어가므로 git 에 섞이지 않게)
OUT = pathlib.Path(os.environ.get("COLLAB_HARNESS_DATA", HOME / ".claude" / "collab-harness"))

WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
REJECTED = "doesn't want to proceed with this tool use"
IDLE_GAP = dt.timedelta(minutes=30)  # 이보다 긴 공백은 작업 시간에서 뺀다

# 내가 AI 결과를 바로잡은 프롬프트. '아니면'·'아니야?'(질문)는 제외한다.
B = r"(?:^|[\s.,!?~;…])"
CORRECTION = re.compile(B + r"(아니(?=[\s,.!?~;…]|$)(?!\s*\?)|아닌데|틀렸|틀린 ?거|잘못(됐|된|했|햇|봤|알|이해)"
                        r"|그게 아니|그 소리가 아니|소통의 오류|다시 (해|봐|짜|만들|확인)|왜 (이렇게|그렇게|자꾸|아까부터))")
# 내가 AI 말을 되물은 프롬프트 (근거·출처·확인 요구, '~아니야?' 반문)
CHALLENGE = re.compile(r"근거|출처|확실해|맞아\?|맞는 ?거야|맞는지|진짜야|확인했어|확인 ?해 ?봐|검증|직접 재|아니야\?|아닌가|아냐\?")
# 검증 성격의 셸 명령 (git diff/checkout 같은 건 제외)
VERIFY_CMD = re.compile(r"pytest|unittest|jest|vitest|npm (run )?test|검증|측정|정확도|verify|validate|\bcheck\b|\bassert\b", re.I)
SCREEN_TOOL = re.compile(r"^mcp__(Claude_Browser|claude-in-chrome)__(read_page|get_page_text|find)$")
SCREEN_ACTIONS = {"screenshot", "zoom"}
PASTED = re.compile(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", re.S)
NOT_TYPED = ("<", "[Request interrupted", "[Earlier usage-limit", "Caveat:", "Base directory for this skill",
             "Continue from where you left off", "This session is being continued")
LLM_LABELS = OUT / "llm_labels.json"  # scripts/llm_classify.py 결과. 있으면 키워드 대신 쓴다
EVAL = OUT / "label_eval.json"        # scripts/heuristic_eval.py score 결과 (정답표 대비 정밀도)

SECTION_KIND = [("틀렸", "M"), ("결정", "D"), ("검증", "V"), ("프롬프트", "P")]


def ts(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def project_name(cwd):
    if not cwd:
        return "(알 수 없음)"
    if "scratch-workspaces" in cwd:
        return "(폴더 없음)"
    p = pathlib.PureWindowsPath(cwd) if "\\" in cwd else pathlib.PurePosixPath(cwd)
    return p.name or str(p)


def typed_text(msg):
    """사람이 직접 친 텍스트만 돌려준다. 도구 결과·시스템 주입은 None."""
    c = msg.get("content")
    if isinstance(c, str):
        parts = [c]
    elif isinstance(c, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
            return None
        parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
    else:
        return None
    parts = [p.strip() for p in parts if p.strip() and not p.lstrip().startswith(NOT_TYPED)]
    text = "\n".join(l for l in "\n".join(parts).splitlines() if not l.startswith("[Image"))
    return text.strip() or None


def own_words(text):
    """붙여넣은 글을 빼고 내가 쓴 부분만 (키워드 판정용)."""
    return PASTED.sub(" ", text)


def prompt_key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def label(text, llm=None):
    """C=바로잡기 / Q=되묻기 / N. LLM 분류 결과가 있으면 그걸, 없으면 키워드 규칙."""
    if llm and prompt_key(text) in llm:
        return llm[prompt_key(text)]
    mine = own_words(text)
    return "C" if CORRECTION.search(mine) else "Q" if CHALLENGE.search(mine) else "N"


def parse_session(jf, llm=None, seen=None):
    """seen: 이미 센 레코드 uuid. 세션을 이어하면 이전 대화가 새 파일에 복사되므로 전역으로 중복을 뺀다."""
    seen = set() if seen is None else seen
    s = dict(prompts=0, corrections=0, challenges=0, tool_calls=0, verify_cmds=0,
             screen_checks=0, rejected=0, files=set(), cwd=None, title=None, stamps=[],
             week_prompts=collections.Counter(), week_corr=collections.Counter(), week_chal=collections.Counter())
    for line in jf.open(encoding="utf-8", errors="replace"):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = d.get("type")
        if t == "custom-title":
            s["title"] = d.get("customTitle")
            continue
        if d.get("isSidechain") or d.get("isMeta"):
            continue
        uid = d.get("uuid")
        if uid:
            if uid in seen:
                continue
            seen.add(uid)
        s["cwd"] = s["cwd"] or d.get("cwd")
        when = ts(d.get("timestamp"))
        if when:
            s["stamps"].append(when)
        msg = d.get("message") or {}
        if t == "user":
            c = msg.get("content")
            if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result"
                                           and REJECTED in json.dumps(b.get("content"), ensure_ascii=False) for b in c):
                s["rejected"] += 1
            text = typed_text(msg)
            if text:
                s["prompts"] += 1
                wk = when.strftime("%G-W%V") if when else "?"
                s["week_prompts"][wk] += 1
                kind = label(text, llm)
                if kind == "C":
                    s["corrections"] += 1
                    s["week_corr"][wk] += 1
                elif kind == "Q":
                    s["challenges"] += 1
                    s["week_chal"][wk] += 1
        elif t == "assistant":
            for b in msg.get("content") or []:
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                name, inp = b.get("name", "?"), b.get("input") or {}
                s["tool_calls"] += 1
                if name in WRITE_TOOLS and inp.get("file_path"):
                    s["files"].add(inp["file_path"])
                elif name in ("Bash", "PowerShell") and VERIFY_CMD.search(inp.get("command", "")):
                    s["verify_cmds"] += 1
                elif SCREEN_TOOL.match(name) or (name.endswith("__computer") and inp.get("action") in SCREEN_ACTIONS):
                    s["screen_checks"] += 1
    st = sorted(s["stamps"])
    s["active_min"] = sum((b - a).total_seconds() for a, b in zip(st, st[1:]) if b - a < IDLE_GAP) / 60
    s["first"], s["last"] = (st[0], st[-1]) if st else (None, None)
    return s


def parse_records(cwd):
    """docs/포트폴리오-기록.md 의 D·V·M·P 개수와 작업기록 항목 수."""
    out = {"D": 0, "V": 0, "M": 0, "P": 0, "logs": 0}
    if not cwd or "scratch-workspaces" in cwd:
        return out
    docs = pathlib.Path(cwd) / "docs"
    rec = docs / "포트폴리오-기록.md"
    if rec.exists():
        for sec in re.split(r"^## ", rec.read_text(encoding="utf-8", errors="replace"), flags=re.M)[1:]:
            title, _, body = sec.partition("\n")
            kind = next((k for word, k in SECTION_KIND if word in title), None)
            if not kind:
                continue
            heads = len(re.findall(r"^### ", body, flags=re.M))
            rows = [l for l in body.splitlines() if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l)]
            out[kind] += heads or max(len(rows) - 1, 0)  # 표만 있으면 헤더 한 줄 뺀다
    log = docs / "작업기록.md"
    if log.exists():
        out["logs"] = len(re.findall(r"^## \d{4}-\d{2}-\d{2}", log.read_text(encoding="utf-8", errors="replace"), flags=re.M))
    return out


def collect(root, since):
    llm = json.loads(LLM_LABELS.read_text(encoding="utf-8")) if LLM_LABELS.exists() else None
    projects, seen = {}, set()
    weeks = collections.defaultdict(lambda: {"prompts": 0, "corrections": 0, "challenges": 0})
    files = sorted(pathlib.Path(root).glob("*/*.jsonl"), key=lambda f: f.stat().st_mtime)  # 원본(먼저 생긴 파일)에 귀속
    for jf in files:
        s = parse_session(jf, llm, seen)
        if not s["prompts"] and not s["tool_calls"]:
            continue
        if since and (not s["last"] or s["last"].date().isoformat() < since):
            continue
        name = project_name(s["cwd"])
        p = projects.setdefault(name, dict(project=name, cwd=s["cwd"], sessions=0, prompts=0, corrections=0,
                                           challenges=0, tool_calls=0, verify_cmds=0, screen_checks=0,
                                           rejected=0, files=set(), active_min=0.0, first=None, last=None))
        p["sessions"] += 1
        for k in ("prompts", "corrections", "challenges", "tool_calls", "verify_cmds", "screen_checks", "rejected", "active_min"):
            p[k] += s[k]
        p["files"] |= s["files"]
        if s["first"]:
            p["first"] = min(p["first"] or s["first"], s["first"])
            p["last"] = max(p["last"] or s["last"], s["last"])
        for wk, n in s["week_prompts"].items():
            weeks[wk]["prompts"] += n
        for wk, n in s["week_corr"].items():
            weeks[wk]["corrections"] += n
        for wk, n in s["week_chal"].items():
            weeks[wk]["challenges"] += n

    rows = []
    for p in projects.values():
        p["files_edited"] = len(p.pop("files"))
        p["active_hours"] = round(p.pop("active_min") / 60, 1)
        p["records"] = parse_records(p["cwd"])
        p["first"] = p["first"].date().isoformat() if p["first"] else None
        p["last"] = p["last"].date().isoformat() if p["last"] else None
        p.pop("cwd")
        rows.append(p)
    rows.sort(key=lambda r: -r["prompts"])

    keys = ("sessions", "prompts", "corrections", "challenges", "tool_calls", "verify_cmds",
            "screen_checks", "rejected", "files_edited", "active_hours")
    total = {k: round(sum(r[k] for r in rows), 1) for k in keys}
    total["records"] = {k: sum(r["records"][k] for r in rows) for k in ("D", "V", "M", "P", "logs")}
    total["tool_calls_per_prompt"] = round(total["tool_calls"] / total["prompts"], 1) if total["prompts"] else 0
    total["human_check_rate"] = round((total["corrections"] + total["challenges"]) / total["prompts"] * 100, 1) if total["prompts"] else 0
    firsts = [r["first"] for r in rows if r["first"]]
    lasts = [r["last"] for r in rows if r["last"]]
    return {
        "generated": dt.datetime.now().isoformat(timespec="minutes"),
        "period": [min(firsts) if firsts else None, max(lasts) if lasts else None],
        "total": total,
        "projects": rows,
        "weeks": [{"week": k, **v} for k, v in sorted(weeks.items()) if k != "?"],
        "label_source": "llm" if llm else "keyword",
        "label_eval": json.loads(EVAL.read_text(encoding="utf-8")) if EVAL.exists() else None,
    }


def report_md(m):
    t, r = m["total"], m["total"]["records"]
    how = "Claude 분류 (직전 AI 답변 포함)" if m["label_source"] == "llm" else "키워드 규칙"
    ev = (m.get("label_eval") or {}).get(m["label_source"]) or {}
    prec = lambda k: f" · 정밀도 {ev[k]['precision']:.0%} (정답표 {ev['n']}건)" if k in ev else ""
    o = [
        "# AI 협업 리포트", "",
        f"- 기간: {m['period'][0]} ~ {m['period'][1]} · 생성: {m['generated']}",
        f"- 세션 **{t['sessions']}개** · 내가 쓴 프롬프트 **{t['prompts']}건** · Claude 도구 호출 **{t['tool_calls']}회** "
        f"(프롬프트 1건당 {t['tool_calls_per_prompt']}회)",
        f"- 실제 작업 시간(30분 이상 공백 제외): **{t['active_hours']}시간** · 수정된 파일 **{t['files_edited']}개**", "",
        "## 사람이 개입한 지점", "",
        "| 지표 | 값 | 어떻게 셌나 |", "| --- | ---: | --- |",
        f"| AI 결과를 바로잡은 프롬프트 | {t['corrections']} | {how}{prec('C')} |",
        f"| AI 말을 되물은 프롬프트 | {t['challenges']} | {how}{prec('Q')} |",
        f"| 개입 비율 | {t['human_check_rate']}% | (바로잡기+되묻기) ÷ 전체 프롬프트 |",
        f"| 도구 실행을 거절한 횟수 | {t['rejected']} | 권한 요청에서 '거절' |",
        f"| 검증 명령 실행 | {t['verify_cmds']} | 테스트·측정·정확도·check 명령 |",
        f"| 브라우저 화면 확인 | {t['screen_checks']} | 브라우저 도구 호출 |", "",
        "## 기록 문서에 남은 것 (docs/포트폴리오-기록.md)", "",
        f"결정 **{r['D']}** · 검증 **{r['V']}** · AI가 틀린 기록 **{r['M']}** · 잘 통한 프롬프트 **{r['P']}** · 작업기록 항목 **{r['logs']}**", "",
        "## 프로젝트별", "",
        "| 프로젝트 | 세션 | 프롬프트 | 바로잡기 | 되묻기 | 검증 | 작업시간 | D/V/M/P | 기간 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for p in m["projects"]:
        rc = p["records"]
        o.append(f"| {p['project']} | {p['sessions']} | {p['prompts']} | {p['corrections']} | {p['challenges']} | "
                 f"{p['verify_cmds'] + p['screen_checks']} | {p['active_hours']}h | {rc['D']}/{rc['V']}/{rc['M']}/{rc['P']} | "
                 f"{p['first']} ~ {p['last']} |")
    o += ["", "## 주별 추이", "", "| 주 | 프롬프트 | 바로잡기 |", "| --- | ---: | ---: |"]
    o += [f"| {w['week']} | {w['prompts']} | {w['corrections']} |" for w in m["weeks"]]
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--since", help="YYYY-MM-DD")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--html", metavar="PATH", help="대시보드 HTML 을 이 경로에 만든다 (숫자만 들어가서 공개해도 된다)")
    a = ap.parse_args()
    if not pathlib.Path(a.root).is_dir():
        sys.exit(f"not found: {a.root}")

    m = collect(a.root, a.since)
    out = pathlib.Path(a.out)
    out.mkdir(exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "report.md").write_text(report_md(m), encoding="utf-8")
    if a.html:
        import collab_dashboard
        pathlib.Path(a.html).write_text(collab_dashboard.render(m), encoding="utf-8")
        print(f"wrote {a.html}")
    t = m["total"]
    print(f"wrote {out}  ({t['sessions']} sessions, {t['prompts']} prompts, {t['corrections']} corrections)")


if __name__ == "__main__":
    main()
