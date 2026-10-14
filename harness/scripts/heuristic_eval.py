"""'바로잡기'·'되묻기' 휴리스틱이 얼마나 맞는지 정답표로 잰다.

    python heuristic_eval.py sample --n 60    # ~/.claude/collab-harness/label.csv 생성 (프롬프트 원문 포함 — 레포 밖에 저장)
    (label.csv 의 truth 칸에 직접 C=바로잡기 / Q=되묻기 / N=둘 다 아님 을 적는다)
    python heuristic_eval.py score            # 키워드 규칙 vs LLM 분류 정밀도 비교 → label_eval.json

표본은 예측 C·Q·N 에서 같은 수씩 뽑는다 (N에서도 뽑아야 놓친 것 = 재현율을 볼 수 있다).
"""
import argparse
import csv
import json
import pathlib
import random

import collab_metrics as cm

LABEL = cm.OUT / "label.csv"


def predict(text):
    mine = cm.own_words(text)
    return "C" if cm.CORRECTION.search(mine) else "Q" if cm.CHALLENGE.search(mine) else "N"


def all_prompts():
    for jf in pathlib.Path(cm.ROOT).glob("*/*.jsonl"):
        for line in jf.open(encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "user" and not d.get("isSidechain"):
                t = cm.typed_text(d.get("message") or {})
                if t:
                    yield " ".join(cm.own_words(t).split())[:300]


def sample(n, seed):
    random.seed(seed)
    buckets = {"C": [], "Q": [], "N": []}
    for t in set(all_prompts()):
        buckets[predict(t)].append(t)
    rows = [(k, t) for k, v in buckets.items() for t in random.sample(sorted(v), min(n // 3, len(v)))]
    random.shuffle(rows)  # 예측값을 보고 라벨링하지 않도록 섞는다
    cm.OUT.mkdir(exist_ok=True)
    with LABEL.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "prompt", "truth", "pred"])
        for i, (k, t) in enumerate(rows):
            w.writerow([i, t, "", k])
    print(f"wrote {LABEL} ({len(rows)} rows). truth 칸을 채운 뒤 score 를 실행하세요. pred 칸은 가리고 보세요.")


def llm_preds():
    """label.csv 의 prompt 칸(내 말 300자) → LLM 라벨."""
    llm = json.loads(cm.LLM_LABELS.read_text(encoding="utf-8")) if cm.LLM_LABELS.exists() else {}
    out = {}
    for jf in pathlib.Path(cm.ROOT).glob("*/*.jsonl"):
        for line in jf.open(encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "user" and not d.get("isSidechain"):
                t = cm.typed_text(d.get("message") or {})
                if t and cm.prompt_key(t) in llm:
                    out[" ".join(cm.own_words(t).split())[:300]] = llm[cm.prompt_key(t)]
    return out


def metrics(rows, pred_of):
    res = {"n": len(rows)}
    for k in ("C", "Q"):
        tp = sum(pred_of(r) == k and r["truth"].upper() == k for r in rows)
        pp = sum(pred_of(r) == k for r in rows)
        ap = sum(r["truth"].upper() == k for r in rows)
        res[k] = {"precision": tp / pp if pp else 0, "recall_in_sample": tp / ap if ap else 0, "tp": tp, "pred": pp, "actual": ap}
    res["accuracy"] = sum(pred_of(r) == r["truth"].upper() for r in rows) / len(rows)
    return res


def score(labeler):
    rows = [r for r in csv.DictReader(LABEL.open(encoding="utf-8-sig")) if r["truth"].strip()]
    if not rows:
        raise SystemExit("truth 가 채워진 줄이 없습니다.")
    llm = llm_preds()
    result = {"labeler": labeler, "keyword": metrics(rows, lambda r: r["pred"])}
    covered = [r for r in rows if r["prompt"] in llm]
    if covered:
        result["llm"] = metrics(covered, lambda r: llm[r["prompt"]])
    print(f"라벨 {len(rows)}건")
    for src, m in ((k, v) for k, v in result.items() if k != "labeler"):
        print(f"[{src}] {m['n']}건 · 3분류 정확도 {m['accuracy']:.0%}")
        for k, name in (("C", "바로잡기"), ("Q", "되묻기")):
            x = m[k]
            print(f"   {name}: 정밀도 {x['precision']:.0%} ({x['tp']}/{x['pred']}) · 표본 내 재현율 {x['recall_in_sample']:.0%} ({x['tp']}/{x['actual']})")
    cm.EVAL.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("※ 표본은 키워드 예측 기준 층화 추출이라 재현율은 표본 안에서의 값입니다.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sample", "score"])
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--labeler", default="본인", help="truth 를 누가 붙였나 (대시보드에 표시)")
    a = ap.parse_args()
    sample(a.n, a.seed) if a.cmd == "sample" else score(a.labeler)


if __name__ == "__main__":
    main()
