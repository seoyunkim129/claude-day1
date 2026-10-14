---
name: collab-report
description: 모든 프로젝트의 Claude Code 세션과 기록 문서를 모아 AI 협업 지표(프롬프트 수, 바로잡기·되묻기, 검증 실행, 작업시간, D/V/M/P 기록 수)를 리포트와 대시보드로 만든다. "협업 리포트", "AI 활용 지표", "내가 AI 얼마나 썼어", "대시보드 갱신", "주간 리포트" 요청에 사용한다.
---

# AI 협업 리포트

스크립트는 이 플러그인의 `scripts/` 폴더에 있다 (`${CLAUDE_PLUGIN_ROOT}/scripts`). 결과와 캐시는 `~/.claude/collab-harness/`에 저장되고, 레포에는 들어가지 않는다.

## 순서

1. **새 프롬프트 분류** — 아직 분류 안 된 프롬프트만 Claude로 분류한다 (캐시가 있어 이미 한 건 다시 안 함).
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/llm_classify.py"
   ```
   실패한 배치가 있으면 한 번 더 실행하면 빠진 것만 처리한다.
2. **지표 계산**
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/collab_metrics.py" [--since YYYY-MM-DD] [--html <경로>]
   ```
   사용자가 대시보드를 원하거나 공개용이면 `--html`로 경로를 지정한다. 대시보드에는 숫자와 프로젝트 이름만 들어간다.
3. `~/.claude/collab-harness/report.md`를 읽고 사용자에게 핵심만 말한다: 기간, 프롬프트 수, 개입 비율, 지난번 대비 변화, 기록(D/V/M/P)이 비어 있는 프로젝트.
4. **분류 품질을 같이 말한다.** `label_eval.json`이 있으면 정답표 대비 정밀도를 함께 보고한다. 없으면 "바로잡기·되묻기 수치는 아직 검증 안 된 근사값"이라고 밝힌다.

## 분류 품질 검증 (사용자가 원할 때)

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/heuristic_eval.py" sample --n 60 --seed <새 숫자>
```
→ `~/.claude/collab-harness/label.csv`의 truth 칸을 **사용자 본인이** 채운다 (C=바로잡기 / Q=되묻기 / N). 본인 의도는 본인이 제일 잘 안다. 그 다음:
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/heuristic_eval.py" score
```

## 지키는 것

- 프롬프트 원문을 답변이나 공개 파일에 옮기지 않는다. label.csv는 사용자 확인용으로만 쓴다.
- 수치를 부풀려 말하지 않는다. 근사값은 근사값이라고 한다.
- 회사 업무 세션이 섞여 있을 수 있으면 공개 전에 프로젝트 목록을 사용자에게 보여주고 뺄 것을 묻는다.
