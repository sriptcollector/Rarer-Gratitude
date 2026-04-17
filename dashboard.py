import os
import sqlite3
import statistics
from urllib.parse import unquote
from flask import Flask, jsonify, render_template_string, request, abort
import config
from strategies.descriptions import get as get_desc
from strategies.explain import _parse as parse_name

app = Flask(__name__)


def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


BASE_CSS = """
<title>Rare Gratitude</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#030603; --panel:#071009; --panel2:#0a1a0e; --border:#0f2415;
    --fg:#c8f5d2; --dim:#4fa968; --mute:#2d6d42;
    --pos:#3fff7a; --neg:#ff4d5e; --accent:#3fff7a;
    --mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
    --sans: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; background:var(--bg); color:var(--fg);
               font-family: var(--sans);
               font-size:15px; -webkit-font-smoothing:antialiased; }
  a { color:inherit; text-decoration:none; }
  a:hover { color:var(--accent); }
  .wrap { max-width:1720px; width:100%; margin:0 auto; padding:36px 48px 80px; }
  header { display:flex; align-items:center; justify-content:space-between;
           padding-bottom:22px; border-bottom:1px solid var(--border); margin-bottom:32px; }
  .brand { display:flex; align-items:center; gap:12px; font-weight:600;
           font-size:17px; letter-spacing:-.015em; }
  .dot { width:8px; height:8px; border-radius:50%; background:var(--pos);
         box-shadow:0 0 10px var(--pos), 0 0 0 3px rgba(63,255,122,.18);
         animation:pulse 2.4s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.45} }
  .nav { display:flex; gap:24px; font-size:14px; color:var(--dim); align-items:center; }
  .nav a { padding:4px 0; transition:color .15s; }
  .nav a.active { color:var(--fg); }
  h1 { font-size:26px; margin:0; font-weight:600; letter-spacing:-.02em; }
  h2 { font-size:12px; color:var(--dim); text-transform:uppercase; letter-spacing:.1em;
       margin:32px 0 14px; font-weight:600; }
  h3 { font-size:13px; color:var(--dim); text-transform:uppercase; letter-spacing:.08em;
       margin:18px 0 8px; font-weight:600; }
  .stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
           gap:14px; margin-bottom:32px; }
  .stat { background:var(--panel); border:1px solid var(--border); border-radius:12px;
          padding:18px 20px; }
  .stat .k { font-size:11.5px; color:var(--dim); text-transform:uppercase; letter-spacing:.08em; margin-bottom:10px; }
  .stat .v { font-size:24px; font-weight:600; font-variant-numeric: tabular-nums; letter-spacing:-.02em; }
  .grid { display:grid; grid-template-columns: 1.5fr 1fr; gap:22px; }
  @media (max-width:960px) { .grid { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--border); border-radius:12px; }
  .panel .hd { padding:14px 20px; border-bottom:1px solid var(--border);
               display:flex; justify-content:space-between; align-items:center;
               font-size:12px; color:var(--dim); text-transform:uppercase; letter-spacing:.08em; }
  .panel .bd { padding:20px; }
  table { width:100%; border-collapse:collapse; font-variant-numeric: tabular-nums; }
  th, td { padding:12px 20px; text-align:left; border-bottom:1px solid var(--border); font-size:14px; }
  th { background:transparent; font-weight:500; color:var(--dim);
       text-transform:uppercase; letter-spacing:.06em; font-size:11px;
       border-bottom:1px solid var(--border); }
  tbody tr:last-child td { border-bottom:none; }
  tr.row { cursor:pointer; transition:background .1s; }
  tr.row:hover { background:var(--panel2); }
  td.num, th.num { text-align:right; }
  .mono { font-family:var(--mono); font-size:13px; }
  .pos { color:var(--pos); }
  .neg { color:var(--neg); }
  .dim { color:var(--dim); }
  .mute { color:var(--mute); }
  .badge { display:inline-block; padding:3px 8px; border-radius:6px;
           background:var(--panel2); font-size:12px; color:var(--dim); font-family:var(--mono); }
  .tag { display:inline-block; padding:4px 10px; border-radius:6px;
         background:rgba(63,255,122,.08); color:var(--pos); font-size:11.5px;
         text-transform:uppercase; letter-spacing:.06em;
         border:1px solid rgba(63,255,122,.2); }
  .empty { padding:40px 20px; text-align:center; color:var(--mute); }
  canvas { width:100% !important; max-height:220px; }
  .rank { color:var(--mute); width:30px; }
  .back { font-size:12px; color:var(--dim); }
  .back:hover { color:var(--fg); }
  .flash { animation: fl 1.3s ease; }
  @keyframes fl { 0%{background:rgba(63,255,122,.28); box-shadow:inset 0 0 18px rgba(63,255,122,.18);}
                  60%{background:rgba(63,255,122,.10);}
                  100%{background:transparent; box-shadow:none;} }
  /* Tooltip */
  .tip { position:relative; cursor:help; border-bottom:1px dotted var(--mute); }
  .tip:hover::after {
    content: attr(data-tip);
    position:absolute; right:0; left:auto; top:calc(100% + 6px);
    background:#0e1117; border:1px solid var(--border);
    padding:10px 12px; border-radius:8px; font-size:12px;
    color:var(--fg); white-space:normal; width:320px; z-index:50;
    box-shadow:0 6px 30px rgba(0,0,0,.5);
    font-family:var(--sans);
    font-weight:normal; letter-spacing:0; text-transform:none;
  }
  /* volatility meter */
  .meter { display:inline-block; vertical-align:middle; height:8px; width:120px;
           background:var(--panel2); border-radius:4px; overflow:hidden;
           border:1px solid var(--border); }
  .meter > div { height:100%; background:linear-gradient(90deg,#22c55e,#f59e0b,#ef4444); }
  .pc { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
  .pc ul { margin:0; padding-left:18px; font-size:13px; line-height:1.55; color:#d1d5db; }
  .pc ul li { margin-bottom:4px; }
  .pc .p h3 { color:#22c55e; }
  .pc .c h3 { color:#ef4444; }
  .blurb { line-height:1.65; color:var(--fg); font-size:13.5px; opacity:.88; }
  .blurb + .blurb { margin-top:10px; }
</style>
"""

NAV = """
<header>
  <div class="brand"><span class="dot"></span> Rare Gratitude</div>
  <div class="nav">
    <a href="/" class="{{ 'active' if active=='home' else '' }}">Overview</a>
    <a href="/leaderboard" class="{{ 'active' if active=='lb' else '' }}">Leaderboard</a>
    <a href="/trades" class="{{ 'active' if active=='trades' else '' }}">Trades</a>
    <a href="/symbols" class="{{ 'active' if active=='symbols' else '' }}">Symbols</a>
    <a href="/newsbot" class="{{ 'active' if active=='news' else '' }}">NewsBot</a>
    <a href="/evolution" class="{{ 'active' if active=='evo' else '' }}">Evolution</a>
    <span class="dim mono" id="clock" style="margin-left:10px">—</span>
  </div>
</header>
"""

HOME = BASE_CSS + """
<div class="wrap">
""" + NAV + """

<div class="stats">
  <div class="stat"><div class="k">Best Return</div><div class="v" id="best">—</div></div>
  <div class="stat"><div class="k">Median Return</div><div class="v" id="med">—</div></div>
  <div class="stat"><div class="k">Strategies</div><div class="v" id="total">—</div></div>
  <div class="stat"><div class="k">Closed Trades</div><div class="v" id="tcount">—</div></div>
  <div class="stat"><div class="k">Open Positions</div><div class="v pos" id="open">—</div></div>
  <div class="stat"><div class="k">Signals / tick</div><div class="v" id="sigs">—</div></div>
</div>
<div class="panel" style="margin-bottom:22px">
  <div class="hd"><span>Fleet Equity — all strategies, cumulative</span><span class="mono dim" id="eqinfo">—</span></div>
  <div class="bd" style="padding:16px"><canvas id="feq" style="max-height:220px"></canvas></div>
</div>

<div class="panel">
  <div class="hd"><span>Live Trades — last 10</span><a href="/trades" class="back">view all →</a></div>
  <table>
    <thead><tr>
      <th>Time</th><th>Symbol</th><th>Strategy</th>
      <th class="num">PnL</th><th>Why</th>
    </tr></thead>
    <tbody id="trades"><tr><td colspan=5 class="empty">no trades yet…</td></tr></tbody>
  </table>
</div>

</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
""" + """
<script>
let lastTs=null; let lastTradeId=null; let fleetChart=null;
const fmtP=x=>(x>=0?'+':'')+x.toFixed(3)+'%';
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const cls=x=>x>0?'pos':x<0?'neg':'dim';
const enc=s=>encodeURIComponent(s);
const esc=s=>(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  try {
    const [m,t,h,eq]=await Promise.all([
      fetch('/api/metrics').then(r=>r.json()),
      fetch('/api/trades?limit=10').then(r=>r.json()),
      fetch('/api/health').then(r=>r.json()),
      fetch('/api/equity_curve').then(r=>r.json()),
    ]);
    const rows=m.strategies||[];
    document.getElementById('total').textContent=rows.length;
    document.getElementById('tcount').textContent=t.total||0;
    document.getElementById('best').innerHTML=rows[0]?`<span class="${cls(rows[0].return_pct)}">${fmtP(rows[0].return_pct)}</span>`:'—';
    const sorted=rows.map(r=>r.return_pct).sort((a,b)=>a-b);
    const med=sorted.length?sorted[Math.floor(sorted.length/2)]:0;
    document.getElementById('med').innerHTML=rows.length?`<span class="${cls(med)}">${fmtP(med)}</span>`:'—';
    document.getElementById('open').textContent=h.open_positions_live??(m.open_positions??'—');
    const a=h.action_tally||{};
    document.getElementById('sigs').textContent=(a.buy||0)+' buy / '+(a.sell||0)+' sell';

    // Fleet equity curve
    const curve=(eq.curve||[]);
    document.getElementById('eqinfo').textContent=curve.length+' snapshots';
    if(curve.length>1){
      const ctx=document.getElementById('feq');
      const data={labels:curve.map(p=>p[0].slice(11,19)),
        datasets:[{data:curve.map(p=>p[1]),borderColor:'#3fff7a',
          backgroundColor:'rgba(63,255,122,.08)',borderWidth:1.5,fill:true,tension:.2,pointRadius:0}]};
      const opts={responsive:true,maintainAspectRatio:false,animation:false,
        plugins:{legend:{display:false}},
        scales:{x:{ticks:{color:'#4fa968',maxTicksLimit:8},grid:{color:'#0f2415'}},
                y:{ticks:{color:'#4fa968',callback:v=>'$'+(v/1000).toFixed(0)+'k'},grid:{color:'#0f2415'}}}};
      if(fleetChart) fleetChart.destroy();
      fleetChart=new Chart(ctx,{type:'line',data,options:opts});
    }

    const tr=t.trades||[];
    const topId=tr[0]?tr[0].id:null;
    document.getElementById('trades').innerHTML=tr.map(x=>`
      <tr class="${lastTradeId!==null && x.id>lastTradeId?'flash':''}">
        <td class="dim mono">${(x.exit_ts||'').slice(11,19)}</td>
        <td><a href="/symbol/${enc(x.symbol)}">${x.symbol}</a></td>
        <td class="mono"><a href="/strategy/${enc(x.strategy)}">${x.strategy.slice(0,32)}</a></td>
        <td class="num ${cls(x.pnl)}">${fmtM(x.pnl)}</td>
        <td class="dim tip" data-tip="${esc(x.explanation||x.reason)}">${x.reason}</td>
      </tr>`).join('') || '<tr><td colspan=5 class="empty">no trades yet…</td></tr>';
    if(topId) lastTradeId=topId;
  } catch(e){ document.getElementById('clock').textContent='disconnected'; }
}
tick(); setInterval(tick, 3000);
</script>
"""

LEADERBOARD = BASE_CSS + """
<div class="wrap">
""" + NAV + """
<h1>Leaderboard</h1>
<div class="dim" style="margin-bottom:20px">Every strategy, ranked by % return. Click a row for detail.</div>
<div class="panel">
<table>
  <thead><tr>
    <th class="rank">#</th><th>Strategy</th><th>Type</th>
    <th class="num">Return</th><th class="num">Win%</th>
    <th class="num">Trades</th><th class="num">PF</th>
    <th class="num">Expectancy</th><th class="num">Max DD</th><th class="num">Equity</th>
  </tr></thead>
  <tbody id="lb"><tr><td colspan=10 class="empty">loading…</td></tr></tbody>
</table>
</div>
</div>
""" + """
<script>
const fmtP=x=>(x>=0?'+':'')+x.toFixed(3)+'%';
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const cls=x=>x>0?'pos':x<0?'neg':'dim';
const enc=s=>encodeURIComponent(s);
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const m=await fetch('/api/metrics').then(r=>r.json());
  const rows=m.strategies||[];
  document.getElementById('lb').innerHTML=rows.map((r,i)=>{
    const cls_ = (r.strategy.match(/^([A-Za-z]+)/) || ['',''])[1];
    return `<tr class="row" onclick="location.href='/strategy/${enc(r.strategy)}'">
      <td class="rank">${i+1}</td>
      <td class="mono">${r.strategy}</td>
      <td><span class="tag">${cls_}</span></td>
      <td class="num ${cls(r.return_pct)}">${fmtP(r.return_pct)}</td>
      <td class="num">${(r.win_rate*100).toFixed(1)}%</td>
      <td class="num">${r.trades}</td>
      <td class="num">${r.profit_factor.toFixed(2)}</td>
      <td class="num ${cls(r.expectancy)}">${fmtM(r.expectancy)}</td>
      <td class="num neg">${(r.max_dd*100).toFixed(2)}%</td>
      <td class="num">$${r.equity.toFixed(2)}</td>
    </tr>`; }).join('') || '<tr><td colspan=10 class="empty">waiting for first snapshot…</td></tr>';
}
tick(); setInterval(tick, 4000);
</script>
"""

STRATEGY = BASE_CSS + """
<div class="wrap">
""" + NAV + """
<a href="/leaderboard" class="back">← leaderboard</a>
<h1 style="margin-top:10px">{{ name }}</h1>
<div class="dim mono" style="font-size:12px;margin-bottom:8px">{{ class_name }} · <span class="tag">{{ desc.regime }}</span></div>

<div class="stats" id="stats"></div>

<div class="grid" style="grid-template-columns: 1.4fr 1fr">
  <div class="panel">
    <div class="hd"><span>Equity Curve</span><span class="mono dim" id="points">—</span></div>
    <div class="bd"><canvas id="eq"></canvas></div>
  </div>
  <div class="panel">
    <div class="hd">Volatility</div>
    <div class="bd">
      <div style="font-size:11px;color:var(--dim);margin-bottom:6px;text-transform:uppercase;letter-spacing:.08em">Equity stddev (stable → wild)</div>
      <div class="meter"><div id="volbar" style="width:0%"></div></div>
      <div id="voltext" class="mono" style="margin-top:8px;font-size:12px;color:var(--dim)">—</div>
      <div style="margin-top:16px;font-size:12px;color:var(--dim)">Return dispersion gives a feel for ride quality. Low = steady; high = big swings.</div>
    </div>
  </div>
</div>

<div class="panel" style="margin-top:22px">
  <div class="hd">About this strategy</div>
  <div class="bd">
    <div class="blurb"><b style="color:#93c5fd">What it is.</b> {{ desc.what }}</div>
    <div class="blurb"><b style="color:#93c5fd">Why it tends to work.</b> {{ desc.why_works }}</div>
    <div id="live_why" class="blurb dim" style="margin-top:14px">Live behavior: loading…</div>
    <h3 style="margin-top:18px">Trade-offs</h3>
    <div class="pc">
      <div class="p">
        <h3>Pros</h3>
        <ul>{% for p in desc.pros %}<li>{{ p }}</li>{% endfor %}</ul>
      </div>
      <div class="c">
        <h3>Cons</h3>
        <ul>{% for c in desc.cons %}<li>{{ c }}</li>{% endfor %}</ul>
      </div>
    </div>
  </div>
</div>

<h2>All Trades</h2>
<div class="panel">
<table>
  <thead><tr>
    <th>Exit Time</th><th>Symbol</th>
    <th class="num">Entry</th><th class="num">Exit</th>
    <th class="num">Qty</th><th class="num">PnL</th><th>Why</th>
  </tr></thead>
  <tbody id="trades"><tr><td colspan=7 class="empty">loading…</td></tr></tbody>
</table>
</div>

</div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
""" + """
<script>
const NAME={{ name_json|safe }};
const enc=s=>encodeURIComponent(s);
const esc=s=>(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const fmtP=x=>(x>=0?'+':'')+x.toFixed(3)+'%';
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const cls=x=>x>0?'pos':x<0?'neg':'dim';
let chart=null;

function computeVolatility(eq){
  if(eq.length<3) return {pct:0, label:'not enough data'};
  const rets=[];
  for(let i=1;i<eq.length;i++){
    const r=(eq[i][1]-eq[i-1][1])/(eq[i-1][1]||1);
    if(isFinite(r)) rets.push(r);
  }
  const mean=rets.reduce((a,b)=>a+b,0)/rets.length;
  const v=rets.reduce((a,b)=>a+(b-mean)*(b-mean),0)/rets.length;
  const sd=Math.sqrt(v)*100;
  const norm=Math.min(100, sd*200);
  let label='very stable';
  if(sd>0.1) label='stable'; if(sd>0.3) label='moderate'; if(sd>0.7) label='volatile'; if(sd>1.5) label='wild';
  return {pct:norm, label:`${label} (σ ${sd.toFixed(3)}%)`};
}

async function load(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const [s,t]=await Promise.all([
    fetch('/api/strategy/'+enc(NAME)).then(r=>r.json()),
    fetch('/api/trades?strategy='+enc(NAME)+'&limit=500').then(r=>r.json()),
  ]);
  const m=s.latest || {};
  document.getElementById('stats').innerHTML=`
    <div class="stat"><div class="k">Return</div><div class="v ${cls(m.return_pct||0)}">${fmtP(m.return_pct||0)}</div></div>
    <div class="stat"><div class="k">Win Rate</div><div class="v">${((m.win_rate||0)*100).toFixed(1)}%</div></div>
    <div class="stat"><div class="k">Profit Factor</div><div class="v">${(m.profit_factor||0).toFixed(2)}</div></div>
    <div class="stat"><div class="k">Trades</div><div class="v">${m.trades||0}</div></div>
    <div class="stat"><div class="k">Expectancy</div><div class="v ${cls(m.expectancy||0)}">${fmtM(m.expectancy||0)}</div></div>
    <div class="stat"><div class="k">Max DD</div><div class="v neg">${((m.max_dd||0)*100).toFixed(2)}%</div></div>
    <div class="stat"><div class="k">Equity</div><div class="v">$${(m.equity||0).toFixed(2)}</div></div>
  `;
  const eq=s.equity_curve||[];
  document.getElementById('points').textContent=eq.length+' points';
  const ctx=document.getElementById('eq');
  const data={labels:eq.map(p=>p[0].slice(11,19)), datasets:[{data:eq.map(p=>p[1]),borderColor:'#7c9aff',backgroundColor:'rgba(124,154,255,.08)',borderWidth:1.5,fill:true,tension:.25,pointRadius:0}]};
  const opts={responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#4d5566',maxTicksLimit:8},grid:{color:'#1e222e'}},y:{ticks:{color:'#4d5566'},grid:{color:'#1e222e'}}}};
  if(chart) chart.destroy();
  chart=new Chart(ctx,{type:'line',data,options:opts});

  const vol=computeVolatility(eq);
  document.getElementById('volbar').style.width=vol.pct+'%';
  document.getElementById('voltext').textContent=vol.label;

  // Live "why it's working" analysis
  const wr=(m.win_rate||0), pf=(m.profit_factor||0), rp=(m.return_pct||0), n=(m.trades||0);
  let why='';
  if(n<5) why='Too few trades yet to judge. Patience.';
  else if(rp>0 && wr>0.55 && pf>1.5) why=`Currently profitable: hit rate ${(wr*100).toFixed(0)}% with winners ${pf.toFixed(1)}× larger than losers — the edge is real on recent data.`;
  else if(rp>0 && wr<0.45) why=`Low win rate (${(wr*100).toFixed(0)}%) but still profitable — the few winners are big. Classic trend-follower shape.`;
  else if(rp>0) why=`Net positive with ${n} trades. Small but consistent edge building.`;
  else if(rp<0 && wr>0.55) why=`Winning often (${(wr*100).toFixed(0)}%) but losing overall — losers are too big relative to winners. Needs tighter stops.`;
  else why=`Underperforming lately (${fmtP(rp)}, ${n} trades). May be in the wrong regime — evolution will rotate it out if it stays here.`;
  document.getElementById('live_why').innerHTML='<b style="color:#93c5fd">Live behavior.</b> '+why;

  document.getElementById('trades').innerHTML=(t.trades||[]).map(x=>`
    <tr>
      <td class="dim mono">${x.exit_ts||''}</td>
      <td><a href="/symbol/${enc(x.symbol)}">${x.symbol}</a></td>
      <td class="num mono">${x.entry.toFixed(4)}</td>
      <td class="num mono">${x.exit.toFixed(4)}</td>
      <td class="num mono">${x.qty.toFixed(4)}</td>
      <td class="num ${cls(x.pnl)}">${fmtM(x.pnl)}</td>
      <td class="dim tip" data-tip="${esc(x.explanation||x.reason)}">${x.reason}</td>
    </tr>`).join('') || '<tr><td colspan=7 class="empty">no trades yet…</td></tr>';
}
load(); setInterval(load, 5000);
</script>
"""

TRADES = BASE_CSS + """
<style>
  .toolbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
             margin-bottom:18px; }
  .toolbar input { background:var(--panel); border:1px solid var(--border);
                   color:var(--fg); font-family:var(--mono); font-size:13px;
                   padding:9px 13px; border-radius:8px; width:280px; outline:none; }
  .toolbar input:focus { border-color:var(--pos);
                         box-shadow:0 0 0 3px rgba(63,255,122,.12); }
  .toolbar input::placeholder { color:var(--mute); }
  .chips { display:flex; flex-wrap:wrap; gap:6px; margin-left:4px; }
  .chip { background:var(--panel); border:1px solid var(--border);
          color:var(--dim); font-family:var(--mono); font-size:11.5px;
          padding:7px 12px; border-radius:6px; cursor:pointer;
          text-transform:uppercase; letter-spacing:.05em; transition:all .12s; }
  .chip:hover { color:var(--fg); border-color:var(--mute); }
  .chip.on { color:var(--bg); background:var(--pos); border-color:var(--pos);
             box-shadow:0 0 12px rgba(63,255,122,.35); }
  .tcount { color:var(--dim); font-family:var(--mono); font-size:12px;
            margin-left:auto; }
</style>
<div class="wrap">
""" + NAV + """
<h1>All Trades</h1>
<div class="toolbar">
  <input id="q" placeholder="search symbol or strategy…" autocomplete="off">
  <div class="chips">
    <div class="chip on" data-f="recent">recent</div>
    <div class="chip" data-f="profit">most profitable</div>
    <div class="chip" data-f="loss">least profitable</div>
    <div class="chip" data-f="volatile">most volatile</div>
    <div class="chip" data-f="wins">wins only</div>
    <div class="chip" data-f="losses">losses only</div>
    <div class="chip" data-f="stops">stop-outs</div>
  </div>
  <div class="tcount" id="tcount">—</div>
</div>
<div class="panel">
<table>
  <thead><tr><th>Exit</th><th>Strategy</th><th>Symbol</th>
  <th class="num">Entry</th><th class="num">Exit</th>
  <th class="num">PnL</th><th>Why</th></tr></thead>
  <tbody id="trades"><tr><td colspan=7 class="empty">loading…</td></tr></tbody>
</table>
</div>
</div>
""" + """
<script>
const enc=s=>encodeURIComponent(s);
const esc=s=>(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const cls=x=>x>0?'pos':x<0?'neg':'dim';
let lastId=null;
let allTrades=[];
let activeFilter='recent';
let query='';

function render(){
  let rows=allTrades.slice();
  if(query){
    const q=query.toLowerCase();
    rows=rows.filter(r=>r.symbol.toLowerCase().includes(q)||r.strategy.toLowerCase().includes(q));
  }
  if(activeFilter==='profit') rows.sort((a,b)=>b.pnl-a.pnl);
  else if(activeFilter==='loss') rows.sort((a,b)=>a.pnl-b.pnl);
  else if(activeFilter==='volatile') rows.sort((a,b)=>Math.abs(b.pnl)-Math.abs(a.pnl));
  else if(activeFilter==='wins') rows=rows.filter(r=>r.pnl>0);
  else if(activeFilter==='losses') rows=rows.filter(r=>r.pnl<=0);
  else if(activeFilter==='stops') rows=rows.filter(r=>r.reason==='stop');
  document.getElementById('tcount').textContent=rows.length+' / '+allTrades.length;
  document.getElementById('trades').innerHTML=rows.slice(0,300).map(x=>`
    <tr class="${lastId!==null && x.id>lastId?'flash':''}">
      <td class="dim mono">${(x.exit_ts||'').slice(0,19)}</td>
      <td class="mono"><a href="/strategy/${enc(x.strategy)}">${x.strategy.slice(0,30)}</a></td>
      <td><a href="/symbol/${enc(x.symbol)}">${x.symbol}</a></td>
      <td class="num mono">${x.entry.toFixed(4)}</td>
      <td class="num mono">${x.exit.toFixed(4)}</td>
      <td class="num ${cls(x.pnl)}">${fmtM(x.pnl)}</td>
      <td class="dim tip" data-tip="${esc(x.explanation||x.reason)}">${x.reason}</td>
    </tr>`).join('') || '<tr><td colspan=7 class="empty">no match…</td></tr>';
}
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const t=await fetch('/api/trades?limit=1000').then(r=>r.json());
  allTrades=t.trades||[];
  render();
  if(allTrades[0]) lastId=allTrades[0].id;
}
document.addEventListener('click',e=>{
  const c=e.target.closest('.chip'); if(!c) return;
  document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
  c.classList.add('on'); activeFilter=c.dataset.f; render();
});
document.addEventListener('input',e=>{
  if(e.target.id==='q'){ query=e.target.value; render(); }
});
tick(); setInterval(tick, 4000);
</script>
"""

SYMBOL = BASE_CSS + """
<div class="wrap">
""" + NAV + """
<a href="/symbols" class="back">← symbols</a>
<h1 style="margin-top:10px">{{ sym }}</h1>
<div class="dim" style="margin-bottom:20px">all trades on this symbol</div>
<div class="panel">
<table>
  <thead><tr><th>Exit</th><th>Strategy</th>
    <th class="num">Entry</th><th class="num">Exit</th>
    <th class="num">PnL</th><th>Why</th></tr></thead>
  <tbody id="trades"><tr><td colspan=6 class="empty">loading…</td></tr></tbody>
</table>
</div>
</div>
""" + """
<script>
const SYM={{ sym_json|safe }};
const enc=s=>encodeURIComponent(s);
const esc=s=>(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const cls=x=>x>0?'pos':x<0?'neg':'dim';
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const t=await fetch('/api/trades?symbol='+enc(SYM)+'&limit=500').then(r=>r.json());
  document.getElementById('trades').innerHTML=(t.trades||[]).map(x=>`
    <tr>
      <td class="dim mono">${(x.exit_ts||'').slice(0,19)}</td>
      <td class="mono"><a href="/strategy/${enc(x.strategy)}">${x.strategy.slice(0,32)}</a></td>
      <td class="num mono">${x.entry.toFixed(4)}</td>
      <td class="num mono">${x.exit.toFixed(4)}</td>
      <td class="num ${cls(x.pnl)}">${fmtM(x.pnl)}</td>
      <td class="dim tip" data-tip="${esc(x.explanation||x.reason)}">${x.reason}</td>
    </tr>`).join('') || '<tr><td colspan=6 class="empty">no trades yet on this symbol…</td></tr>';
}
tick(); setInterval(tick, 4000);
</script>
"""

SYMBOLS = BASE_CSS + """
<div class="wrap">
""" + NAV + """
<h1>Symbols</h1>
<div class="dim" style="margin-bottom:20px">aggregated trade activity per symbol</div>
<div class="panel">
<table>
  <thead><tr><th>Symbol</th><th class="num">Trades</th><th class="num">Win%</th><th class="num">Net PnL</th></tr></thead>
  <tbody id="tb"><tr><td colspan=4 class="empty">loading…</td></tr></tbody>
</table>
</div>
</div>
""" + """
<script>
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const cls=x=>x>0?'pos':x<0?'neg':'dim';
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const d=await fetch('/api/symbols').then(r=>r.json());
  document.getElementById('tb').innerHTML=(d.symbols||[]).map(r=>`
    <tr class="row" onclick="location.href='/symbol/'+encodeURIComponent('${r.symbol}')">
      <td>${r.symbol}</td>
      <td class="num">${r.trades}</td>
      <td class="num">${(r.win_rate*100).toFixed(1)}%</td>
      <td class="num ${cls(r.pnl)}">${fmtM(r.pnl)}</td>
    </tr>`).join('') || '<tr><td colspan=4 class="empty">no trades yet…</td></tr>';
}
tick(); setInterval(tick, 5000);
</script>
"""

EVOLUTION = BASE_CSS + """
<div class="wrap">
""" + NAV + """
<h1>Evolution Log</h1>
<div class="dim" style="margin-bottom:20px">
Each cycle (every 24h): bottom 20% of strategies by return are killed; top 20% spawn mutated offspring with jittered params. Offspring names end in <span class="badge">-g2, -g3, …</span>
</div>
<div class="panel">
<table>
  <thead><tr><th>When</th><th>Killed</th><th>Born</th></tr></thead>
  <tbody id="tb"><tr><td colspan=3 class="empty">no evolution yet — first cycle after 24h uptime</td></tr></tbody>
</table>
</div>
</div>
""" + """
<script>
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const d=await fetch('/api/evolution').then(r=>r.json());
  const rows=d.cycles||[];
  if(!rows.length) return;
  document.getElementById('tb').innerHTML=rows.map(r=>`
    <tr>
      <td class="dim mono">${new Date(r.ts*1000).toLocaleString()}</td>
      <td class="mono">${(r.killed||'').split(',').slice(0,4).join(', ')||'—'} <span class="dim">(${(r.killed||'').split(',').filter(Boolean).length})</span></td>
      <td class="mono">${(r.born||'').split(',').slice(0,4).join(', ')||'—'} <span class="dim">(${(r.born||'').split(',').filter(Boolean).length})</span></td>
    </tr>`).join('');
}
tick(); setInterval(tick, 10000);
</script>
"""


NEWSBOT = BASE_CSS + """
<div class="wrap">
""" + NAV + """
<h1>NewsBot</h1>
<div class="dim" style="margin-bottom:22px">Scans CryptoCompare headlines every minute, opens aggressive paper positions on strong bullish sentiment (score ≥ +2), closes on bearish reversals or stops.</div>

<div class="stats" id="nbstats"></div>

<div class="panel" style="margin-bottom:22px">
  <div class="hd"><span>Signal Feed</span><span class="mono dim" id="newsinfo">—</span></div>
  <table>
    <thead><tr>
      <th>When</th><th>Sentiment</th><th>Symbols</th><th>Headline</th><th>Source</th><th>Action</th>
    </tr></thead>
    <tbody id="newsbody"><tr><td colspan=6 class="empty">waiting for news…</td></tr></tbody>
  </table>
</div>

<h2>NewsBot Trades</h2>
<div class="panel">
<table>
  <thead><tr><th>Exit</th><th>Symbol</th>
    <th class="num">Entry</th><th class="num">Exit</th>
    <th class="num">Qty</th><th class="num">PnL</th><th>Why</th></tr></thead>
  <tbody id="nbtrades"><tr><td colspan=7 class="empty">no news trades yet…</td></tr></tbody>
</table>
</div>
</div>
""" + """
<script>
const enc=s=>encodeURIComponent(s);
const esc=s=>(s||'').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const fmtM=x=>(x>=0?'+':'')+x.toFixed(2);
const fmtP=x=>(x>=0?'+':'')+x.toFixed(3)+'%';
const cls=x=>x>0?'pos':x<0?'neg':'dim';
let lastNewsId=null, lastTradeId=null;
function sentTag(s){
  if(s>=2) return '<span class="tag" style="color:var(--pos);border-color:rgba(63,255,122,.3)">bullish +'+s+'</span>';
  if(s<=-2) return '<span class="tag" style="color:var(--neg);background:rgba(244,77,94,.1);border-color:rgba(244,77,94,.3)">bearish '+s+'</span>';
  return '<span class="tag" style="color:var(--dim);background:transparent">neutral '+(s>0?'+':'')+s+'</span>';
}
async function tick(){
  document.getElementById('clock').textContent=new Date().toLocaleTimeString();
  const [m,n,t]=await Promise.all([
    fetch('/api/strategy/NewsBot').then(r=>r.json()),
    fetch('/api/news?limit=50').then(r=>r.json()),
    fetch('/api/trades?strategy=NewsBot&limit=100').then(r=>r.json()),
  ]);
  const s=m.latest||{};
  document.getElementById('nbstats').innerHTML=`
    <div class="stat"><div class="k">Return</div><div class="v ${cls(s.return_pct||0)}">${fmtP(s.return_pct||0)}</div></div>
    <div class="stat"><div class="k">Trades</div><div class="v">${s.trades||0}</div></div>
    <div class="stat"><div class="k">Win Rate</div><div class="v">${((s.win_rate||0)*100).toFixed(1)}%</div></div>
    <div class="stat"><div class="k">Profit Factor</div><div class="v">${(s.profit_factor||0).toFixed(2)}</div></div>
    <div class="stat"><div class="k">Equity</div><div class="v">$${(s.equity||0).toFixed(2)}</div></div>
    <div class="stat"><div class="k">Max DD</div><div class="v neg">${((s.max_dd||0)*100).toFixed(2)}%</div></div>
  `;
  const items=n.items||[];
  document.getElementById('newsinfo').textContent=items.length+' headlines';
  const topNid=items[0]?items[0].id:null;
  document.getElementById('newsbody').innerHTML=items.map(x=>{
    const when=x.ts?new Date(x.ts*1000).toLocaleTimeString():'—';
    const syms=(x.symbols||'').split(',').filter(Boolean).join(' ');
    return `<tr class="${lastNewsId!==null && x.id>lastNewsId?'flash':''}">
      <td class="dim mono">${when}</td>
      <td>${sentTag(x.sentiment||0)}</td>
      <td class="mono">${syms||'<span class="mute">—</span>'}</td>
      <td><a href="${esc(x.url)}" target="_blank">${esc((x.title||'').slice(0,110))}</a></td>
      <td class="dim">${esc(x.source||'')}</td>
      <td>${x.traded?'<span class="tag">TRADED</span>':'<span class="mute">—</span>'}</td>
    </tr>`;
  }).join('') || '<tr><td colspan=6 class="empty">waiting for news…</td></tr>';
  if(topNid) lastNewsId=topNid;
  const tr=t.trades||[];
  const topTid=tr[0]?tr[0].id:null;
  document.getElementById('nbtrades').innerHTML=tr.map(x=>`
    <tr class="${lastTradeId!==null && x.id>lastTradeId?'flash':''}">
      <td class="dim mono">${(x.exit_ts||'').slice(0,19)}</td>
      <td><a href="/symbol/${enc(x.symbol)}">${x.symbol}</a></td>
      <td class="num mono">${x.entry.toFixed(4)}</td>
      <td class="num mono">${x.exit.toFixed(4)}</td>
      <td class="num mono">${x.qty.toFixed(4)}</td>
      <td class="num ${cls(x.pnl)}">${fmtM(x.pnl)}</td>
      <td class="dim tip" data-tip="${esc(x.explanation||x.reason)}">${x.reason}</td>
    </tr>`).join('') || '<tr><td colspan=7 class="empty">no news trades yet…</td></tr>';
  if(topTid) lastTradeId=topTid;
}
tick(); setInterval(tick, 5000);
</script>
"""


@app.route("/")
def index():
    return render_template_string(HOME, active="home")


@app.route("/newsbot")
def newsbot_page():
    return render_template_string(NEWSBOT, active="news")


@app.route("/api/news")
def api_news():
    limit = min(int(request.args.get("limit", 50)), 500)
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT id, ts, title, url, source, sentiment, symbols, traded "
            "FROM news ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        items = [dict(r) for r in rows]
    except sqlite3.OperationalError:
        items = []
    conn.close()
    return jsonify({"items": items})


@app.route("/leaderboard")
def leaderboard():
    return render_template_string(LEADERBOARD, active="lb")


@app.route("/trades")
def trades_page():
    return render_template_string(TRADES, active="trades")


@app.route("/symbols")
def symbols_page():
    return render_template_string(SYMBOLS, active="symbols")


@app.route("/evolution")
def evolution_page():
    return render_template_string(EVOLUTION, active="evo")


@app.route("/strategy/<path:name>")
def strategy_page(name):
    name = unquote(name)
    import json as _j
    cls, _ = parse_name(name)
    desc = get_desc(cls)
    return render_template_string(
        STRATEGY, active="lb", name=name, class_name=cls, desc=desc,
        name_json=_j.dumps(name),
    )


@app.route("/symbol/<path:sym>")
def symbol_page(sym):
    import json as _j
    sym = unquote(sym)
    return render_template_string(SYMBOL, active="symbols", sym=sym, sym_json=_j.dumps(sym))


@app.route("/api/metrics")
def api_metrics():
    conn = _conn()
    ts = conn.execute("SELECT MAX(ts) FROM metrics").fetchone()[0]
    rows = []
    if ts:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM metrics WHERE ts=? ORDER BY return_pct DESC, win_rate DESC", (ts,))]
    conn.close()
    open_pos = None
    try:
        with open(os.path.join(os.path.dirname(config.DB_PATH) or ".", "open_positions.txt")) as f:
            open_pos = int(f.read().strip() or "0")
    except Exception:
        pass
    return jsonify({"ts": ts, "strategies": rows, "open_positions": open_pos})


@app.route("/api/trades")
def api_trades():
    strategy = request.args.get("strategy")
    symbol = request.args.get("symbol")
    limit = min(int(request.args.get("limit", 50)), 1000)
    conn = _conn()
    q = "SELECT * FROM trades WHERE 1=1"
    args = []
    if strategy:
        q += " AND strategy=?"; args.append(strategy)
    if symbol:
        q += " AND symbol=?"; args.append(symbol)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    trades = [dict(r) for r in conn.execute(q, args)]
    total = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    return jsonify({"total": total, "trades": trades})


@app.route("/api/strategy/<path:name>")
def api_strategy(name):
    name = unquote(name)
    conn = _conn()
    latest_ts = conn.execute("SELECT MAX(ts) FROM metrics WHERE strategy=?", (name,)).fetchone()[0]
    latest = {}
    if latest_ts:
        row = conn.execute("SELECT * FROM metrics WHERE strategy=? AND ts=?", (name, latest_ts)).fetchone()
        if row: latest = dict(row)
    curve = conn.execute(
        "SELECT ts, equity FROM metrics WHERE strategy=? ORDER BY ts", (name,)).fetchall()
    conn.close()
    return jsonify({"name": name, "latest": latest, "equity_curve": [[r[0], r[1]] for r in curve]})


@app.route("/api/symbols")
def api_symbols():
    conn = _conn()
    rows = conn.execute("""
        SELECT symbol,
               COUNT(*) AS trades,
               SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) AS win_rate,
               SUM(pnl) AS pnl
        FROM trades GROUP BY symbol ORDER BY trades DESC
    """).fetchall()
    conn.close()
    return jsonify({"symbols": [dict(r) for r in rows]})


@app.route("/api/equity_curve")
def api_equity_curve():
    """Aggregate equity curve: sum of all strategy equities over time."""
    conn = _conn()
    rows = conn.execute(
        "SELECT ts, SUM(equity) as total_equity, COUNT(*) as n "
        "FROM metrics GROUP BY ts ORDER BY ts"
    ).fetchall()
    conn.close()
    points = [[r["ts"], r["total_equity"], r["n"]] for r in rows]
    return jsonify({"curve": points})


@app.route("/api/health")
def api_health():
    from engine.state import state as _st
    conn = _conn()
    latest_metric_ts = conn.execute("SELECT MAX(ts) FROM metrics").fetchone()[0]
    latest_trade = conn.execute(
        "SELECT id, exit_ts, strategy FROM trades ORDER BY id DESC LIMIT 1"
    ).fetchone()
    trade_count = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    news_count = 0
    try:
        news_count = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    except sqlite3.OperationalError:
        pass
    conn.close()
    return jsonify({
        "latest_metric_ts": latest_metric_ts,
        "latest_trade": dict(latest_trade) if latest_trade else None,
        "trade_count": trade_count,
        "news_count": news_count,
        "exchange": config.EXCHANGE,
        "timeframe": config.TIMEFRAME,
        "quote": config.QUOTE,
        "active_symbols": _st.get("symbols", []),
        "bar_counts": _st.get("bar_counts", {}),
        "active_bar_symbols": _st.get("active_bar_symbols", []),
        "last_tick_ts": _st.get("last_tick_ts"),
        "last_tick_ms": _st.get("last_tick_ms"),
        "open_positions_live": _st.get("open_positions", 0),
        "strat_errors": dict(list((_st.get("strat_errors") or {}).items())[:10]),
        "strat_error_count": _st.get("strat_error_count", 0),
        "action_tally": _st.get("action_tally", {}),
    })


@app.route("/api/evolution")
def api_evolution():
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM evolution ORDER BY ts DESC LIMIT 50").fetchall()
        cycles = [dict(r) for r in rows]
    except sqlite3.OperationalError:
        cycles = []
    conn.close()
    return jsonify({"cycles": cycles})


if __name__ == "__main__":
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
    sqlite3.connect(config.DB_PATH).close()
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False)
