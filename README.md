# collab-harness — AI와 일한 과정을 자동으로 증거로 남기는 하네스

> "AI를 쓸 줄 안다"가 아니라 **"AI가 틀린 걸 어떻게 잡아왔는지"를 숫자로** 보여주기 위해 만든 Claude Code 플러그인.

여러 프로젝트(자수하자, XAI 팀 연구, 포트폴리오 제작 등)를 Claude Code로 진행하면서 "결정·검증·AI 오류를 기록한다"는 규칙을 CLAUDE.md에 적어 쓰고 있었다. 하지만 규칙을 새 폴더마다 복사해야 했고, 기록은 AI에게 매번 부탁해야 했고, 전체적으로 얼마나 개입했는지는 셀 수 없었다. 이 레포는 그 작업 방식을 **설치 한 번으로 재사용할 수 있는 도구**로 묶은 것이다.

대시보드: [`docs/dashboard.html`](docs/dashboard.html) (단일 파일, 브라우저로 열기)

## 무엇을 하나

| 구성 | 하는 일 |
| --- | --- |
| `/collab-harness:new-project` 스킬 | 새 폴더에 CLAUDE.md(일하는 규칙) + 작업기록 + 포트폴리오-기록 템플릿을 깐다 |
| `/collab-harness:record` 스킬 | 단계가 끝나면 결정(D)·검증(V)·AI가 틀린 것(M)·잘 통한 프롬프트(P)를 정해진 형식으로 남긴다 |
| SessionEnd 훅 | 세션이 끝나면 `docs/세션로그.md`에 프롬프트 수·도구 호출·검증 실행·작업시간을 자동으로 한 줄 남긴다 (opt-in 폴더만) |
| `/collab-harness:collab-report` 스킬 | 모든 프로젝트 세션을 모아 지표 리포트와 대시보드를 만든다 |

## 지금까지의 숫자 (2026-08-11 ~ 2026-10-14)

| 지표 | 값 |
| --- | ---: |
| 내가 쓴 프롬프트 (중복 제거) | 831 |
| 실제 협업 시간 (30분 이상 공백 제외) | 96.6시간 |
| 프롬프트 1건당 Claude 작업 수 | 6.4회 |
| 바로잡기·되묻기 비율 | 31.5% (아래 정밀도 참고) |
| 기록된 결정 / 검증 / AI 오류 | 58 / 42 / 39 |

## 측정을 측정하기: 분류기 개선 과정

"AI를 바로잡은 프롬프트"를 세는 게 핵심 지표인데, 이 숫자를 믿을 수 있는지부터 확인했다.

| 버전 | 방법 | 3분류 정확도 | 바로잡기 정밀도 | 되묻기 정밀도 |
| --- | --- | ---: | ---: | ---: |
| v0 | 키워드 ('아니·틀렸·다시 해') | 미측정 | 미측정 — 표본 30건을 읽어보니 '아니면'·붙여넣은 공고문이 대부분 | 미측정 |
| v1 | 키워드 개선 ('아니면'·붙여넣은 글 제외) | 55% | 45% | 40% |
| v2 | Claude 분류 (직전 AI 답변을 같이 보여줌) | 69% | 46% | 78% |
| v3 | Claude 분류 + 기준 명확화·예시 + 번호 밀림 검사 | **72%** | **61%** | 53% |

- 정답표: 프롬프트 60건 층화 표본. **현재 라벨은 Claude가 붙인 임시값**이고, 본인 재검수 후 다시 잰다 (`heuristic_eval.py sample/score`).
- 키워드가 안 통한 이유: 이 사용자는 "아니"를 말버릇으로 써서("아니 블로그가 생각보다 요물이었네") 단어만으로는 교정인지 구분이 안 된다.
- 측정 중 발견한 버그: 세션을 이어하면 이전 대화가 새 파일에 복사돼 프롬프트가 **2.5배(2,148 → 847)** 부풀려지고 있었다. uuid로 중복을 뺐다. 기존 `scripts/claude_session_report.py`도 데스크톱 앱 입력(리스트 형식)을 못 세는 문제가 있었다.

## 설치

```bash
claude plugin marketplace add seoyunkim129/claude-day1
claude plugin install collab-harness@seoyun-harness
```

로컬에서 바로 쓰려면 `claude plugin marketplace add <이 레포 경로>`.

## 직접 실행

```bash
python harness/scripts/llm_classify.py          # 새 프롬프트만 Claude로 분류 (claude -p 사용, API 키 불필요)
python harness/scripts/collab_metrics.py --html docs/dashboard.html
python harness/scripts/heuristic_eval.py sample --n 60   # 정답표 만들기
python harness/scripts/heuristic_eval.py score           # 키워드 vs Claude 정밀도
```

결과와 캐시는 `~/.claude/collab-harness/`에 저장된다. 프롬프트 원문이 들어가는 파일(label.csv)은 레포 밖에만 있고, 대시보드에는 숫자와 프로젝트 이름만 들어간다.

## 설계에서 정한 것

- **사람이 판단하는 지점을 센다**: 바로잡기, 되묻기, 도구 실행 거절, 검증 실행. "AI를 얼마나 썼나"보다 "어디서 개입했나"가 AX에서 중요한 질문이라고 봤다.
- **opt-in 훅**: `docs/작업기록.md`가 있는 폴더에서만 세션로그를 쓴다. 다른 폴더나 회사 업무 폴더에는 아무것도 쓰지 않는다.
- **훅은 절대 세션을 막지 않는다**: 예외는 삼키고 0으로 끝낸다.
- **수치의 출처를 같이 표시한다**: 키워드인지 Claude 분류인지, 정답표를 누가 붙였는지 대시보드에 나온다.

## 레포 구성

```
.claude-plugin/marketplace.json   마켓플레이스 정의
harness/                          플러그인 본체
  hooks/hooks.json                SessionEnd 훅
  scripts/                        collab_metrics · llm_classify · heuristic_eval · collab_dashboard · session_log
  skills/                         new-project · record · collab-report
docs/                             이 프로젝트의 작업기록 · 포트폴리오-기록 · 대시보드
scripts/                          인턴 시절 만든 노션·카카오 연동, 세션 리포트 (이전 작업)
portfolio/                        포트폴리오 사이트 빌더 (이전 작업)
```
