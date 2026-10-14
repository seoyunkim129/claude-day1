"""Fill _template.html and emit the single-file portfolio.

    python build.py                 -> index.html (paper)
    python build.py --palette cyan  -> index.html with a different default

Images are embedded as data URIs so the output stays one portable file.
"""
import argparse
import base64
import datetime
import pathlib
import re

HERE = pathlib.Path(__file__).parent
ASSETS = HERE / "assets"

# ─────────────────────────────────────────────────────────── work
WORK = [
    dict(
        idx="W / 01", title="라이선스 매출 계보 정비",
        lead="대시보드에서 특정 연도 매출이 사라져 있었습니다. 데이터가 없어서가 아니라 "
             "집계 규칙이 걸러내고 있었습니다.",
        meta=[("기간", "2026.06 — 2026.08"), ("역할", "원인 분석 · 수정 · 회귀 검증"),
              ("기술", "Snowflake · Python · SQL"), ("소속", "SAMG · BI팀")],
        res=["라이선스를 판별하는 기준 컬럼이 <b>해당 연도만 비어 있어</b> 집계에서 제외되고 있음을 확인",
             "판별 기준을 표시 칸에서 <b>계정과목</b>으로 바꿔 누락 매출 전체를 복원",
             "기준이 옳다는 근거로 인접 연도에서 두 기준이 <b>금액까지 1:1 일치</b>함을 확인",
             "변경 후 <b>인접 연도 숫자가 그대로인지</b> 검증하고 나서야 완료로 처리",
             "근본 해결(원천 소급 입력)과 현재 우회를 구분해 문서에 남김"],
        kpi=[("55.7억", "복원 매출"), ("0건", "인접 연도 변동"), ("98.6%", "카테고리 부착률")],
        link=None,
    ),
    dict(
        idx="W / 02", title="재고 파이프라인 설계",
        lead="현업의 머릿속에만 있던 재고 판정 규칙을 인터뷰로 꺼내 "
             "검증 가능한 데이터 모델로 옮겼습니다.",
        meta=[("기간", "2026.07 — 2026.08"), ("역할", "규칙 수집 · 모델 설계 · 검증"),
              ("기술", "Snowflake · SQL"), ("소속", "SAMG · BI팀")],
        res=["출고가 두 종류(즉시 매출 차감 / 창고 이동 후 일괄 차감)이며 창고 관점에선 "
             "<b>합산해야 한다</b>는 규칙을 확인",
             "<b>전일재고 + 입고 − 출고 = 당일재고</b> 대사식을 세우고 파일 기준 시점을 맞춰 97% 일치",
             "설명되지 않는 3%는 원천 파일이 없는 항목이라 <b>'미설명 차이'로 명시</b>",
             "신선도 잔여율 구간이 채널 수용 기준과 연결됨을 반영해 4구간으로 정의",
             "날짜에 따라 매일 값이 바뀌는 지표는 <b>저장하지 않고 뷰로 분리</b>",
             "재고량 대신 <b>소진일수</b>를 핵심 지표로 두어 정체 상품을 탐지"],
        kpi=[("97%", "대사 일치율"), ("3층", "RAW · 가공 · 뷰"), ("5개", "정립한 판정 규칙")],
        link=None,
    ),
    dict(
        idx="W / 03", title="팀 전용 AI 에이전트 구축",
        lead="한국어로 물으면 답하되, 담당 범위 밖 데이터는 조회 수단 자체를 두지 않는 "
             "방식으로 격리했습니다.",
        meta=[("기간", "2026.07 — 2026.08"), ("역할", "설계 · 구축 · 검증 · 문서화"),
              ("기술", "Snowflake Cortex · SQL"), ("소속", "SAMG · BI팀")],
        res=["연결 도구를 <b>하나로 제한</b>해 범위 밖 질문에는 답할 근거 자체가 없도록 구성",
             "지표 정의가 빠지면 에러 없이 <b>0을 반환하는 실패 모드</b>를 발견하고 대사로 확인",
             "지시문에 데이터 기간 상한·범위 밖 안내를 명시해 <b>추측 답변을 차단</b>",
             "권한을 사람이 아닌 <b>역할에 부여</b>하고 4계층으로 분리",
             "보조 역할이 살아 있으면 차단이 통과되는 것을 발견, <b>해제 상태에서 격리 재검증</b>",
             "구축 절차와 실패 사례를 매뉴얼로 정리해 다음 팀이 반복할 수 있게 함"],
        kpi=[("4겹", "권한 계층"), ("1개", "연결 도구"), ("4권", "작성 매뉴얼")],
        link=None,
    ),
    dict(
        idx="W / 04", title="ABSA 기반 한국어 화장품 리뷰 속성별 감성 분류",
        lead="\"가격은 비싸지만 효과는 좋아요\"처럼 한 문장에 섞인 속성별 감성을 "
             "분리해 분류하는 시스템을 설계했습니다.",
        meta=[("기간", "2026.03 — 2026.06"), ("역할", "1저자 · 크롤링 제외 전 과정"),
              ("기술", "Python · PyTorch · KLUE-BERT · KLUE-RoBERTa · Streamlit"),
              ("데이터", "한국어 화장품 리뷰 (부정·중립·긍정 3클래스)")],
        res=["<b>[CLS] text [SEP] aspect [SEP]</b> 입력 구조로 동일 문장 내 속성별 감성 분리가 "
             "실제로 동작함을 실험으로 검증",
             "RoBERTa가 token_type_ids를 쓰지 않음에도 <b>전 지표에서 소폭 우위</b> — "
             "사전학습 데이터 규모 차이를 원인으로 분석",
             "정확도만이 아니라 <b>클래스별 F1</b>을 함께 봐서 중립 클래스 불균형을 구체적으로 식별",
             "Streamlit 데모로 비개발자도 결과를 확인할 수 있게 전달",
             "구동 중 개인화 만족도 수식 오류와 <b>리뷰 수가 적은 제품의 상위권 독점</b>을 직접 발견, "
             "최소 리뷰 수 필터와 가중치 재조정으로 보완 계획 수립"],
        kpi=[("0.9435", "Test Accuracy"), ("0.8921", "F1 macro"), ("1저자", "논문 작성")],
        link=("github.com/seoyunkim129/korean-cosmetic-absa",
              "https://github.com/seoyunkim129/korean-cosmetic-absa"),
    ),
    dict(
        idx="W / 05", title="외국인 카드소비 분석 · Travely Pass 전략",
        lead="관광 소비에 생활형 소비가 섞여 있다는 가설을 세우고 "
             "통계적으로 분리한 뒤 전략을 도출했습니다.",
        meta=[("기간", "2025.07 — 2025.10"), ("역할", "분석 전 과정 단독 수행"),
              ("기술", "Python · Pandas · Seaborn · Scikit-learn (K-means)"),
              ("데이터", "통계청 외국인 카드소비 데이터")],
        res=["구 × 업종 히트맵에서 특정 지역 생활형 업종 비중이 <b>70~80%</b>로 튀는 것을 먼저 포착",
             "외국인 근로자 수와 생활형 소비 비중 간 회귀분석으로 혼입 가능성 검증 (<b>p &lt; 0.001</b>)",
             "비관광 업종을 제거한 분석용 데이터셋을 재구축해 신뢰도 확보",
             "대만: 연 약 <b>0.51조 원</b> 소비, 전체 대비 8.7%, 평균 대비 객단가 약 30% 높음",
             "K-means로 관광·쇼핑형 / 생활형 / 복합형 국가군을 구분하고 <b>차기 확장 국가</b>를 제안",
             "팀원이 직접 쓸 수 있는 엑셀 동적 대시보드와 보고서로 전달"],
        kpi=[("p &lt; 0.001", "혼입 검증"), ("0.51조", "대만 연간 소비"), ("30%", "객단가 우위")],
        link=("github.com/seoyunkim129/Internship-Project…",
              "https://github.com/seoyunkim129/Internship-Project-Analysis-of-Foreigner-Card-Spending-Patterns"),
    ),
    dict(
        idx="W / 06", title="디지털 금융 전환에 따른 고령층 금융 소외",
        lead="필요한 데이터가 공개돼 있지 않아, 분석 가능한 환경 자체를 "
             "직접 만드는 것부터 시작했습니다.",
        meta=[("기간", "2026.04 — 진행 중"), ("역할", "조장 · 기획 100% · 수집 및 전처리 100%"),
              ("기술", "Python · BeautifulSoup · Requests"),
              ("데이터", "전국은행연합회 크롤링 5,514건 (서울·부산·인천)")],
        res=["UI상 50페이지로 표시되던 목록이 실제 <b>276페이지</b>임을 이진탐색으로 확인하고 전량 수집",
             "SSL 인증 오류 · 실제 페이지 수 불일치 · 주소 기반 지역명 오분류 · 폐지 행정구역명 "
             "<b>4가지 정합성 문제</b>를 직접 해결",
             "서울에서 가설이 기각되자 데이터 탓 대신 <b>상업지 점포 과밀이라는 구조적 편향</b>을 규명",
             "분석 범위를 부산·인천으로 재설계해 도시별 양상을 비교",
             "인천 옹진군 은행 점포 <b>0개</b> 등 실제 금융 사막 가능성 확인"],
        kpi=[("5,514건", "구축 데이터셋"), ("276p", "실제 페이지 수"), ("3개 도시", "분석 범위")],
        link=("github.com/seoyunkim129/data-visualization",
              "https://github.com/seoyunkim129/data-visualization"),
    ),
]

SKILLS = [
    ("Python", 3, "Pandas · NumPy 기반 데이터 파이프라인 / Scikit-learn · Statsmodels OLS · "
                  "PyTorch KLUE-BERT/RoBERTa 모델링"),
    ("SQL", 2, "집계 · 조인 그레인 · 이중집계 회피 / 파생 집계층 정의 및 대사 검증"),
    ("Snowflake", 2, "RAW 적재 · 다이나믹 테이블 · 역할 기반 권한 · Cortex 시맨틱 뷰"),
    ("Streamlit", 2, "Snowflake 내 업로드 앱 운영 / ABSA 모델 결과 시각화 데모 구현"),
    ("BeautifulSoup / Requests", 2, "전국은행연합회 5,514건 수집 / SSL 오류 · 페이지 불일치 등 "
                                    "정합성 문제 직접 해결"),
    ("Seaborn / Matplotlib / Folium", 2, "구 × 업종 히트맵 · 버블차트 · 인터랙티브 지도 등 "
                                         "분석 목적 맞춤 시각화"),
]


def data_uri(name):
    b = (ASSETS / name).read_bytes()
    return "data:image/webp;base64," + base64.b64encode(b).decode()


def render_work():
    out = []
    for w in WORK:
        meta = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in w["meta"])
        res = "".join(f"<li>{r}</li>" for r in w["res"])
        kpi = "".join(f'<div><div class="v">{v}</div><div class="k ko-label">{k}</div></div>'
                      for v, k in w["kpi"])
        link = ""
        if w["link"]:
            label, href = w["link"]
            link = (f'<a class="lnk" href="{href}" target="_blank" rel="noopener">'
                    f'<span class="mono">{label}</span><span class="mono">↗</span></a>')
        out.append(f"""      <article class="wk rv">
        <div class="wk-in">
          <div class="wk-l">
            <div class="wk-idx">{w['idx']}</div>
            <h3>{w['title']}</h3>
            <p class="lead">{w['lead']}</p>
            <dl>{meta}</dl>
            {link}
          </div>
          <div class="wk-r">
            <ul class="res">{res}</ul>
            <div class="kpi">{kpi}</div>
          </div>
        </div>
      </article>""")
    return "\n".join(out)


def render_skills():
    out = []
    for name, lvl, desc in SKILLS:
        bars = "".join(f'<i class="{"f" if i < lvl else ""}"></i>' for i in range(3))
        out.append(f'        <div class="skrow"><span class="nm">{name}</span>'
                   f'<span class="lvl">{bars}</span>'
                   f'<span class="ds">{desc}</span></div>')
    return "\n".join(out)


def to_artifact(html):
    """Strip the document wrapper — Artifact supplies doctype/html/head/body itself.

    The bare :root block already carries the paper palette, so losing the
    data-palette attribute on <html> changes nothing; ?palette= still works
    because the page script sets it on documentElement at runtime.
    """
    head = html.split("<head>", 1)[1].split("</head>", 1)[0]
    body = html.split("<body>", 1)[1].rsplit("</body>", 1)[0]
    for pattern in (r'\s*<meta charset[^>]*>', r'\s*<meta name="viewport"[^>]*>'):
        head = re.sub(pattern, "", head)          # the host sets both
    return head.strip() + "\n\n" + body.strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--palette", default="paper")
    ap.add_argument("--out", default="index.html")
    ap.add_argument("--phone", default="",
                    help="phone number for the contact row. Left out entirely when "
                         "omitted — never hardcode it here, this file is public")
    ap.add_argument("--artifact", action="store_true",
                    help="emit wrapper-less markup for publishing as an Artifact")
    a = ap.parse_args()

    phone_row = ""
    if a.phone:
        tel = "".join(c for c in a.phone if c.isdigit())
        phone_row = ('        <div class="pf-row"><span class="ko-label">연락처</span>'
                     f'<span><a href="tel:{tel}">{a.phone}</a></span></div>')

    html = (HERE / "_template.html").read_text(encoding="utf-8")
    for token, value in {
        "{{PALETTE}}": a.palette,
        "{{BUILD_DATE}}": datetime.date.today().isoformat(),
        "{{HERO_IMG}}": data_uri("hero.webp"),
        "{{PROFILE_IMG}}": data_uri("profile.webp"),
        "{{WORK}}": render_work(),
        "{{SKILLS}}": render_skills(),
        "{{PHONE_ROW}}": phone_row,
    }.items():
        html = html.replace(token, value)

    if "{{" in html:
        raise SystemExit("unreplaced token remains: " +
                         html[html.index("{{"):html.index("{{") + 40])

    if a.artifact:
        html = to_artifact(html)

    out = HERE / a.out
    out.write_text(html, encoding="utf-8")
    print(f"{out.name}  {out.stat().st_size/1024:.0f} KB  palette={a.palette}")


if __name__ == "__main__":
    main()
