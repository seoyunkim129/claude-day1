"""프롬프트를 Claude로 분류한다: C=AI 결과 바로잡기 / Q=AI 말 되묻기·검증 요구 / N=둘 다 아님.

키워드 규칙은 '아니'를 말버릇으로 쓰는 경우를 못 걸러서 정밀도가 40%대였다.
직전 AI 답변을 같이 보여주고 판정시킨다. `claude -p`(로그인된 Claude Code)를 쓰므로 API 키가 필요 없다.

    python llm_classify.py                 # 아직 분류 안 된 프롬프트만 처리 → ~/.claude/collab-harness/llm_labels.json
    python llm_classify.py --limit 100     # 시험 삼아 100건만
    python heuristic_eval.py score --llm   # 정답표로 정밀도 확인

결과는 프롬프트 해시로 캐시한다. 원문은 저장하지 않는다.
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import pathlib
import re
import shutil
import subprocess

import collab_metrics as cm

CLAUDE = shutil.which("claude") or "claude"  # Windows에선 claude.cmd

SYSTEM = """너는 사람-AI 협업 로그를 분류하는 평가자다. 각 항목에는 직전 AI 답변(ai)과 그 뒤 사람이 쓴 메시지(user)가 있다.
user 메시지를 아래 중 하나로 분류해라.

C = 바로잡기: 사람이 "AI가 틀렸다/의도와 다르게 했다/잊었다"는 것을 드러내며 고치게 함.
    판단 기준: AI의 직전 결과·이해·행동에 대한 불만이나 지적이 메시지에 들어 있어야 한다.
    예) "그게 아니라 ~", "왜 이걸 하고 있어", "아까 ~하기로 했잖아", "내가 말한 파일이 있을 텐데", "구분해야 의미가 있지;;", "2번은 완전 별론데"
Q = 되묻기: AI가 말한 사실·근거·계획을 의심하거나, AI에게 결과를 확인·검증하라고 요구함.
    예) "출처가 불분명하지 않나", "진짜 논문이 없다고?", "배포한 거 맞아?", "배포 다시 한번 확인해봐", "작성요령을 확인한 게 맞는지 모르겠네", "~하면 되는 거 아닌가?"
N = 둘 다 아님: 새 지시, 수정·추가·삭제 요청("빼줘", "바꿔줘", "다시 봐줘", "정리해줘"), 정보 제공, 에러 메시지 붙여넣기, 단순 질문, 동의, 고민, 잡담.
    AI가 틀렸다는 표시 없이 내용만 바꾸라는 요청은 N이다. '아니'가 말버릇·감탄으로만 쓰였으면 N.

C와 Q가 섞이면 C. 출력은 JSON 배열 하나만: [{"i":번호,"h":"user 앞 6글자","l":"C|Q|N"}, ...] 다른 말은 쓰지 마라."""


def key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def pairs():
    """(key, 직전 AI 답변 요약, 내 프롬프트) — 중복 제거."""
    seen = set()
    for jf in sorted(pathlib.Path(cm.ROOT).glob("*/*.jsonl")):
        last_ai = ""
        for line in jf.open(encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("isSidechain"):
                continue
            msg = d.get("message") or {}
            if d.get("type") == "assistant":
                txt = " ".join(b.get("text", "") for b in msg.get("content") or [] if isinstance(b, dict) and b.get("type") == "text")
                if txt.strip():
                    last_ai = " ".join(txt.split())
            elif d.get("type") == "user":
                t = cm.typed_text(msg)
                if t:
                    k = key(t)
                    if k not in seen:
                        seen.add(k)
                        yield k, last_ai[-500:], " ".join(cm.own_words(t).split())[:600]


def classify(batch, model):
    items = "\n".join(json.dumps({"i": i, "ai": ai, "user": u}, ensure_ascii=False) for i, (_, ai, u) in enumerate(batch))
    r = subprocess.run(
        [CLAUDE, "-p", "--model", model, "--no-session-persistence",
         "--tools", "", "--output-format", "text"],
        # Windows .cmd 래퍼가 여러 줄 인자를 잘라서 지시문도 stdin으로 넘긴다
        input=SYSTEM + "\n\n" + items, capture_output=True, text=True, encoding="utf-8", timeout=600)
    m = re.search(r"\[.*\]", r.stdout, re.S)
    if not m:
        raise RuntimeError((r.stderr or r.stdout)[:300])
    out = {}
    for o in json.loads(m.group(0)):
        i = o.get("i")
        # 번호가 밀려 다른 프롬프트에 라벨이 붙는 걸 막는다: 앞 글자가 안 맞으면 버리고 다음 실행 때 다시 분류
        if isinstance(i, int) and i < len(batch) and o.get("l") in ("C", "Q", "N")                 and o.get("h", "")[:3].replace(" ", "") in batch[i][2][:12].replace(" ", ""):
            out[batch[i][0]] = o["l"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--batch", type=int, default=20)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()

    labels = json.loads(cm.LLM_LABELS.read_text(encoding="utf-8")) if cm.LLM_LABELS.exists() else {}
    todo = [p for p in pairs() if p[0] not in labels]
    todo = todo[: a.limit] if a.limit else todo
    batches = [todo[i:i + a.batch] for i in range(0, len(todo), a.batch)]
    print(f"분류 대상 {len(todo)}건 / 배치 {len(batches)}개 (이미 분류됨 {len(labels)}건)")

    done = 0
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for fut in cf.as_completed([ex.submit(classify, b, a.model) for b in batches]):
            try:
                labels.update(fut.result())
            except Exception as e:  # 한 배치가 실패해도 나머지는 저장한다. 다시 돌리면 빠진 것만 처리
                print("  배치 실패:", e)
            done += 1
            cm.OUT.mkdir(exist_ok=True)
            cm.LLM_LABELS.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
            print(f"  {done}/{len(batches)} 배치 완료 · 누적 {len(labels)}건")


if __name__ == "__main__":
    main()
