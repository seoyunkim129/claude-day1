"""SessionEnd 훅: 세션이 끝나면 그 프로젝트의 docs/세션로그.md 에 한 줄을 남긴다.

- docs/작업기록.md 가 있는 프로젝트에서만 동작한다 (/collab-harness:new-project 로 만든 폴더 = opt-in).
- 프롬프트 원문은 남기지 않는다. 날짜·세션 제목·숫자만.
- 같은 세션을 이어하면 그 세션 줄을 새 값으로 바꾼다.
- 어떤 경우에도 세션 종료를 막지 않도록 예외는 삼키고 0으로 끝낸다.
"""
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import collab_metrics as cm  # noqa: E402

HEADER = """# 세션 로그

> 세션이 끝날 때마다 collab-harness 훅이 자동으로 한 줄씩 남깁니다. 손으로 고치지 않습니다.
> '바로잡기·되묻기'는 키워드 규칙 값입니다(정밀도 40%대). 정확한 값은 `/collab-harness:collab-report`로 다시 셉니다.

| 날짜 | 세션 | 제목 | 프롬프트 | 바로잡기 | 되묻기 | 도구 호출 | 수정 파일 | 검증 | 작업시간(분) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
"""


def main():
    hook = json.loads(sys.stdin.read() or "{}")
    cwd = pathlib.Path(hook.get("cwd") or ".")
    transcript = pathlib.Path(hook.get("transcript_path") or "")
    docs = cwd / "docs"
    if not (docs / "작업기록.md").exists() or not transcript.is_file():
        return
    s = cm.parse_session(transcript)
    if not s["prompts"]:
        return
    sid = (hook.get("session_id") or transcript.stem)[:8]
    title = re.sub(r"[|\n]", " ", s["title"] or "-")[:40]
    row = (f"| {s['first'].date() if s['first'] else '-'} | `{sid}` | {title} | {s['prompts']} | {s['corrections']} | "
           f"{s['challenges']} | {s['tool_calls']} | {len(s['files'])} | {s['verify_cmds'] + s['screen_checks']} | "
           f"{round(s['active_min'])} |")
    log = docs / "세션로그.md"
    text = log.read_text(encoding="utf-8") if log.exists() else HEADER
    lines = [l for l in text.splitlines() if f"`{sid}`" not in l]
    log.write_text("\n".join(lines).rstrip("\n") + "\n" + row + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 훅 실패가 세션 종료를 방해하면 안 된다
        print(f"collab-harness session_log: {e}", file=sys.stderr)
    sys.exit(0)
