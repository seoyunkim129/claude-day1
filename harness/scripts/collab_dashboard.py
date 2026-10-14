"""metrics.json → 단일 파일 대시보드 HTML (외부 라이브러리 없음, 숫자와 프로젝트 이름만 포함).

    python collab_metrics.py --html docs/dashboard.html
"""

import json

PAGE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 협업 대시보드</title>
<style>
:root{
  color-scheme:light;
  --surface:#fcfcfb; --card:#ffffff; --line:#e6e5e1; --grid:#efeeea;
  --ink:#0b0b0b; --ink2:#52514e; --muted:#8a8984;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --base:#c9c8c3;
}
@media (prefers-color-scheme:dark){
  :root:where(:not([data-theme="light"])){
    color-scheme:dark;
    --surface:#1a1a19; --card:#222220; --line:#383835; --grid:#2c2c2a;
    --ink:#ffffff; --ink2:#c3c2b7; --muted:#8f8e86;
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --base:#55544f;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --surface:#1a1a19; --card:#222220; --line:#383835; --grid:#2c2c2a;
  --ink:#ffffff; --ink2:#c3c2b7; --muted:#8f8e86;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --base:#55544f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font:15px/1.6 Pretendard,"Noto Sans KR","Malgun Gothic",system-ui,sans-serif;word-break:keep-all}
.wrap{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.4px}
h2{font-size:17px;margin:0 0 4px}
.sub{color:var(--ink2);margin:0 0 24px}
.note{color:var(--muted);font-size:13px;margin:6px 0 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:20px}
.tile,.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.tile b{display:block;font-size:30px;line-height:1.1;letter-spacing:-.6px;font-variant-numeric:tabular-nums}
.tile span{color:var(--ink2);font-size:13px}
.card{margin-bottom:16px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:13px;color:var(--ink2);margin:8px 0}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
svg{display:block;width:100%;height:auto;overflow:visible}
.chart{overflow-x:auto}
.chart svg{min-width:640px}
svg text{fill:var(--muted);font-size:11px}
.tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:13px;box-shadow:0 4px 16px #0002;display:none;z-index:9}
table{width:100%;border-collapse:collapse;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{color:var(--ink2);font-weight:600}
.scroll{overflow-x:auto}
.cmp{display:grid;grid-template-columns:110px 1fr 48px;gap:6px 10px;align-items:center;font-size:13px;margin-top:10px}
.bar{height:14px;border-radius:0 4px 4px 0;background:var(--s1)}
.bar.base{background:var(--base)}
.track{background:var(--grid);border-radius:0 4px 4px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:720px){.grid2{grid-template-columns:1fr}}
.grid2 .card{margin-bottom:0}
</style>
</head>
<body>
<div class="wrap">
  <h1>AI 협업 대시보드</h1>
  <p class="sub" id="sub"></p>
  <div class="tiles" id="tiles"></div>

  <div class="card">
    <h2>주별 프롬프트 — 내가 AI를 바로잡고 되물은 비중</h2>
    <div class="legend"><span><i style="background:var(--s2)"></i>바로잡기</span><span><i style="background:var(--s3)"></i>되묻기</span><span><i style="background:var(--s1)"></i>그 외 지시·질문</span></div>
    <div class="chart" id="weeks"></div>
  </div>

  <div class="card">
    <h2>프로젝트별</h2>
    <div class="legend"><span><i style="background:var(--s2)"></i>바로잡기</span><span><i style="background:var(--s3)"></i>되묻기</span><span><i style="background:var(--s1)"></i>그 외</span></div>
    <div class="chart" id="projects"></div>
    <div class="scroll"><table id="ptable"></table></div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>분류기 품질 — 키워드 규칙 vs Claude 분류</h2>
      <p class="note" id="evalnote"></p>
      <div id="eval"></div>
    </div>
    <div class="card">
      <h2>기록 문서에 남은 증거</h2>
      <p class="note">각 프로젝트 docs/포트폴리오-기록.md 에서 센 항목 수</p>
      <div class="scroll"><table id="rtable"></table></div>
    </div>
  </div>
  <p class="note" id="foot"></p>
</div>
<div class="tip" id="tip"></div>
<script>
const M = __DATA__;
const $ = id => document.getElementById(id);
const fmt = n => Number(n).toLocaleString("ko-KR");
const T = M.total, R = T.records;
$("sub").textContent = `${M.period[0]} ~ ${M.period[1]} · Claude Code 세션 ${fmt(T.sessions)}개 · 생성 ${M.generated.replace("T"," ")}`;
[[fmt(T.prompts),"내가 쓴 프롬프트"],[T.active_hours+"시간","실제 협업 시간 (30분 이상 공백 제외)"],
 [T.tool_calls_per_prompt+"회","프롬프트 1건당 Claude 작업 수"],[T.human_check_rate+"%","바로잡기·되묻기 비율"],
 [fmt(R.M),"기록된 'AI가 틀린 것'"],[fmt(T.verify_cmds+T.screen_checks),"검증 실행 (테스트·측정·화면 확인)"]]
 .forEach(([v,l]) => $("tiles").insertAdjacentHTML("beforeend", `<div class="tile"><b>${v}</b><span>${l}</span></div>`));

const tip = $("tip");
function showTip(e, h){ tip.innerHTML = h; tip.style.display = "block";
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8); tip.style.left = x + "px"; tip.style.top = (e.clientY + 14) + "px"; }
const hideTip = () => tip.style.display = "none";
const NS = "http://www.w3.org/2000/svg";
const el = (t, a) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); return n; };
// 아래쪽이 기준선에 붙고 위쪽만 4px 둥근 막대
function vbar(x, y, w, h, r){ r = Math.min(r, h, w/2); return `M${x},${y+h}V${y+r}Q${x},${y} ${x+r},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h}Z`; }
function hbar(x, y, w, h, r){ r = Math.min(r, w, h/2); return `M${x},${y}H${x+w-r}Q${x+w},${y} ${x+w},${y+r}V${y+h-r}Q${x+w},${y+h} ${x+w-r},${y+h}H${x}Z`; }
const parts = d => [["corrections","바로잡기","var(--s2)"],["challenges","되묻기","var(--s3)"],["rest","그 외","var(--s1)"]]
  .map(([k,l,c]) => ({k,l,c,v: k==="rest" ? d.prompts-d.corrections-d.challenges : d[k]}));

// 주별 누적 막대
(function(){
  const W = M.weeks, w = 960, h = 260, L = 36, B = 28, top = 10;
  const max = Math.max(...W.map(d => d.prompts)) * 1.08, bw = (w - L) / W.length;
  const s = el("svg", {viewBox:`0 0 ${w} ${h}`, role:"img", "aria-label":"주별 프롬프트 누적 막대"});
  const y = v => top + (h - B - top) * (1 - v / max);
  const step = Math.pow(10, Math.floor(Math.log10(max))) * (max > 400 ? 2 : 1);
  for (let v = 0; v <= max; v += step){ s.append(el("line",{x1:L,x2:w,y1:y(v),y2:y(v),stroke:"var(--grid)"})); const t = el("text",{x:L-6,y:y(v)+4,"text-anchor":"end"}); t.textContent = v; s.append(t); }
  W.forEach((d, i) => {
    const x = L + i * bw + bw * .18, bwid = bw * .64; let acc = 0;
    const ps = parts(d), last = ps.filter(p => p.v > 0).length - 1;
    ps.filter(p => p.v > 0).forEach((p, j) => {
      const y0 = y(acc + p.v), hh = y(acc) - y0 - (j ? 2 : 0); acc += p.v;
      s.append(el("path",{d: j === last ? vbar(x, y0, bwid, Math.max(hh,0), 4) : `M${x},${y0}h${bwid}v${Math.max(hh,0)}h${-bwid}Z`, fill:p.c}));
    });
    const lab = el("text",{x:x+bwid/2,y:h-10,"text-anchor":"middle"}); lab.textContent = d.week.slice(5); s.append(lab);
    const hit = el("rect",{x:L+i*bw,y:top,width:bw,height:h-B-top,fill:"transparent"});
    hit.addEventListener("mousemove", e => showTip(e, `<b>${d.week}</b><br>프롬프트 ${d.prompts}건<br>바로잡기 ${d.corrections} · 되묻기 ${d.challenges}`));
    hit.addEventListener("mouseleave", hideTip); s.append(hit);
  });
  $("weeks").append(s);
})();

// 프로젝트별 가로 누적 막대 + 표
(function(){
  const P = M.projects.filter(p => p.prompts > 0), w = 960, rowh = 30, L = 110, h = P.length * rowh + 6;
  const max = Math.max(...P.map(p => p.prompts));
  const s = el("svg",{viewBox:`0 0 ${w} ${h}`, role:"img", "aria-label":"프로젝트별 프롬프트"});
  P.forEach((p, i) => {
    const y = i * rowh + 6, bh = 16; let x = L;
    const t = el("text",{x:L-8,y:y+12,"text-anchor":"end"}); t.textContent = p.project; t.style.fill = "var(--ink2)"; t.style.fontSize = "12px"; s.append(t);
    const ps = parts(p).filter(q => q.v > 0);
    ps.forEach((q, j) => {
      const ww = (w - L - 60) * q.v / max - (j < ps.length - 1 ? 2 : 0);
      s.append(el("path",{d: j === ps.length - 1 ? hbar(x, y, Math.max(ww,0), bh, 4) : `M${x},${y}h${Math.max(ww,0)}v${bh}h${-Math.max(ww,0)}Z`, fill:q.c}));
      x += ww + 2;
    });
    const v = el("text",{x:x+4,y:y+12}); v.textContent = p.prompts; v.style.fill = "var(--ink2)"; s.append(v);
    const hit = el("rect",{x:0,y:y-6,width:w,height:rowh,fill:"transparent"});
    hit.addEventListener("mousemove", e => showTip(e, `<b>${p.project}</b><br>세션 ${p.sessions} · 프롬프트 ${p.prompts}<br>바로잡기 ${p.corrections} · 되묻기 ${p.challenges}<br>작업 ${p.active_hours}시간 · ${p.first} ~ ${p.last}`));
    hit.addEventListener("mouseleave", hideTip); s.append(hit);
  });
  $("projects").append(s);
  $("ptable").innerHTML = "<tr><th>프로젝트</th><th>세션</th><th>프롬프트</th><th>바로잡기</th><th>되묻기</th><th>검증 실행</th><th>도구 거절</th><th>작업시간</th></tr>" +
    P.map(p => `<tr><td>${p.project}</td><td>${p.sessions}</td><td>${p.prompts}</td><td>${p.corrections}</td><td>${p.challenges}</td><td>${p.verify_cmds+p.screen_checks}</td><td>${p.rejected}</td><td>${p.active_hours}h</td></tr>`).join("");
  $("rtable").innerHTML = "<tr><th>프로젝트</th><th>결정 D</th><th>검증 V</th><th>AI 오류 M</th><th>프롬프트 P</th><th>작업기록</th></tr>" +
    M.projects.filter(p => Object.values(p.records).some(v => v)).map(p => `<tr><td>${p.project}</td><td>${p.records.D}</td><td>${p.records.V}</td><td>${p.records.M}</td><td>${p.records.P}</td><td>${p.records.logs}</td></tr>`).join("") +
    `<tr><td><b>합계</b></td><td><b>${R.D}</b></td><td><b>${R.V}</b></td><td><b>${R.M}</b></td><td><b>${R.P}</b></td><td><b>${R.logs}</b></td></tr>`;
})();

// 분류기 비교
(function(){
  const E = M.label_eval;
  if (!E){ $("evalnote").textContent = "아직 정답표로 검증하지 않았습니다. 바로잡기·되묻기 수치는 근사값입니다."; return; }
  $("evalnote").textContent = `정답표 ${E.keyword.n}건(라벨: ${E.labeler || "미상"})으로 잰 정밀도. 대시보드 수치는 ${M.label_source === "llm" ? "Claude 분류" : "키워드 규칙"} 기준입니다.`;
  const rows = [["3분류 정확도", E.keyword.accuracy, E.llm && E.llm.accuracy], ["바로잡기 정밀도", E.keyword.C.precision, E.llm && E.llm.C.precision], ["되묻기 정밀도", E.keyword.Q.precision, E.llm && E.llm.Q.precision]];
  let h = "";
  rows.forEach(([l, a, b]) => {
    h += `<div class="cmp"><span>${l}</span><div class="track"><div class="bar base" style="width:${a*100}%"></div></div><span>${Math.round(a*100)}%</span></div>`;
    if (b != null) h += `<div class="cmp" style="margin-top:2px"><span></span><div class="track"><div class="bar" style="width:${b*100}%"></div></div><span><b>${Math.round(b*100)}%</b></span></div>`;
  });
  $("eval").innerHTML = `<div class="legend"><span><i style="background:var(--base)"></i>키워드 규칙</span><span><i style="background:var(--s1)"></i>Claude 분류</span></div>` + h;
})();
$("foot").textContent = "프롬프트 원문은 포함하지 않습니다. 세션을 이어할 때 복사되는 이전 대화는 중복 제거했습니다. collab-harness로 자동 생성.";
</script>
</body>
</html>
"""


def render(m):
    data = json.dumps(m, ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("__DATA__", data)


if __name__ == "__main__":
    import pathlib
    import sys
    import collab_metrics as cm
    m = json.loads((cm.OUT / "metrics.json").read_text(encoding="utf-8"))
    out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else cm.OUT / "dashboard.html")
    out.write_text(render(m), encoding="utf-8")
    print("wrote", out)
