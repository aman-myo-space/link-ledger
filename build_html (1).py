import json

d = json.load(open(".cache/snapshot.json"))
h = json.load(open(".cache/health.json"))

HTML = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Link Ledger</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);
 --bg:#0d0f14;--panel:#151922;--panel2:#1c2130;--line:#2a3142;--fg:#e8ecf4;--mut:#8a94a8;
 --acc:#4d8ef7;--warn:#f5a524;--bad:#f5555d;--good:#3ecf8e}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-size:14px;line-height:1.5;
 font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif}
header{padding:22px 24px 14px;border-bottom:1px solid var(--line)}
h1{margin:0;font-size:19px;font-weight:650;letter-spacing:-.3px}
.sub{color:var(--mut);font-size:12.5px;margin-top:3px}
h3{font-size:13.5px;margin:22px 0 8px;font-weight:600}
.kpis{display:flex;flex-wrap:wrap;gap:10px;padding:16px 24px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:112px;flex:1}
.kpi .v{font-size:23px;font-weight:660;letter-spacing:-.5px}
.kpi .l{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.tabs{display:flex;gap:2px;padding:0 24px;border-bottom:1px solid var(--line);overflow-x:auto}
.tab{padding:10px 16px;cursor:pointer;color:var(--mut);border-bottom:2px solid transparent;white-space:nowrap;font-size:13px}
.tab.on{color:var(--fg);border-bottom-color:var(--acc)}
.pane{display:none;padding:18px 24px 60px}.pane.on{display:block}
.note{color:var(--mut);font-size:12.5px;margin:0 0 14px}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:12.5px;min-width:560px}
th{text-align:left;padding:9px 12px;color:var(--mut);font-weight:550;font-size:11px;text-transform:uppercase;
 letter-spacing:.4px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--panel2)}
td{padding:9px 12px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:none}tr:hover td{background:var(--panel2)}
tr.grp td{background:var(--panel2);font-weight:620}
.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.pill{display:inline-block;padding:1px 7px;border-radius:99px;font-size:10.5px;background:var(--panel2);border:1px solid var(--line);color:var(--mut)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:middle}
.bad{color:var(--bad)}.warn{color:var(--warn)}.good{color:var(--good)}
#graph{width:100%;height:620px;background:var(--panel);border:1px solid var(--line);border-radius:10px}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:10px 0 12px}
.lgrp{display:flex;flex-direction:column;gap:5px}
.lgrp .hd{font-size:10.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--mut)}
.lg{display:flex;align-items:center;gap:6px;font-size:11.5px;background:var(--panel);border:1px solid var(--line);
 padding:3px 9px;border-radius:99px;cursor:pointer;white-space:nowrap}
.lg.off{opacity:.3}
.tip{position:fixed;pointer-events:none;background:#000;border:1px solid var(--line);border-radius:8px;
 padding:8px 11px;font-size:11.5px;max-width:270px;opacity:0;z-index:99}
</style></head><body>

<header><h1>Link Ledger</h1>
<div class="sub">How the MyOperator blog links together, and what it earns &middot; <span id="date"></span></div></header>
<div class="kpis" id="kpis"></div>
<div class="tabs">
  <div class="tab on" data-p="orphans">Orphans</div>
  <div class="tab" data-p="pairs">Link opportunities</div>
  <div class="tab" data-p="clusters">Topics</div>
  <div class="tab" data-p="graph">Graph</div>
  <div class="tab" data-p="broken">Broken links</div>
  <div class="tab" data-p="dead">404s</div>
  <div class="tab" data-p="health">Reader behaviour</div>
</div>
<div class="pane on" id="p-orphans"></div><div class="pane" id="p-pairs"></div>
<div class="pane" id="p-clusters"></div><div class="pane" id="p-graph"></div>
<div class="pane" id="p-broken"></div><div class="pane" id="p-dead"></div>
<div class="pane" id="p-health"></div>
<div class="tip" id="tip"></div>

<script>
const D = __PAYLOAD__, H = __HEALTH__;
const fmt = n => (+n).toLocaleString();
const short = u => u.replace('https://myoperator.com/blog/','').replace('https://myoperator.com','');
document.getElementById('date').textContent = D.generated;
const T = D.totals;

document.getElementById('kpis').innerHTML = [
 ['Blogs', fmt(T.blogs), ''],
 ['Orphans', fmt(T.orphans), 'bad'],
 ['Internal links', fmt(T.edges), ''],
 ['Broken links', fmt(T.broken_link_instances), 'bad'],
 ['404s ranking', fmt(T.dead_urls), 'bad'],
 ['Scroll depth', H.scroll.long+'%', 'warn']
].map(([l,v,c])=>`<div class="kpi"><div class="v ${c}">${v}</div><div class="l">${l}</div></div>`).join('');

function table(cols, rows){
  return '<div class="wrap"><table><thead><tr>'+cols.map(c=>`<th class="${c.n?'num':''}">${c.t}</th>`).join('')+
  '</tr></thead><tbody>'+rows.map(r=>{
    const cls = r.__grp?' class="grp"':'';
    return `<tr${cls}>`+r.map((c,i)=>`<td class="${cols[i].n?'num':''}">${c}</td>`).join('')+'</tr>';
  }).join('')+'</tbody></table></div>';
}

// ORPHANS
const orph = D.nodes.filter(n=>n.inbound===0).sort((a,b)=>b.impr-a.impr);
document.getElementById('p-orphans').innerHTML =
 `<p class="note">Blogs that nothing else on the site links to. Start at the top: these already get search traffic.</p>`+
 table([{t:'Blog'},{t:'Topic'},{t:'Clicks',n:1},{t:'Impressions',n:1},{t:'CTR',n:1},{t:'Position',n:1},{t:'Links out',n:1},{t:'Broken',n:1}],
  orph.map(n=>[`<a href="${n.id}" target="_blank">${short(n.id)}</a>`,
   `<span class="dot" style="background:${n.colour}"></span>${n.sub}`,
   fmt(n.clicks), fmt(n.impr), n.ctr+'%', n.pos, n.outbound_blog,
   n.dead_links?`<span class="bad">${n.dead_links}</span>`:'&mdash;']));

// PAIRS
document.getElementById('p-pairs').innerHTML =
 `<p class="note">Blogs covering the same topic that don't link to each other. Add a link from the left column to the right.</p>`+
 table([{t:'Add a link from'},{t:'Pointing to'},{t:'Match',n:1},{t:'Clicks it has',n:1},{t:'Links it has',n:1}],
  D.pairs.slice(0,150).map(p=>[`<a href="${p.from}" target="_blank">${short(p.from)}</a>`,
   `<a href="${p.to}" target="_blank">${short(p.to)}</a>`, Math.round(p.sim*100)+'%', fmt(p.from_clicks),
   p.to_inbound===0?'<span class="bad">0</span>':p.to_inbound]));

// CLUSTERS
const crows = [];
D.parents.forEach(p=>{
  const r = [`<span class="dot" style="background:${p.colour}"></span><b>${p.name}</b>`, p.pages, fmt(p.clicks),
             fmt(p.impr), p.internal_links, p.density, p.orphans];
  r.__grp = true; crows.push(r);
  D.clusters.filter(c=>c.parent===p.name && !(p.name==='Other')).forEach(c=>{
    crows.push([`<span style="padding-left:18px"><span class="dot" style="background:${c.colour}"></span>${c.sub}</span>`,
      c.pages, fmt(c.clicks), fmt(c.impr), c.internal_links,
      `<span class="${c.density<1?'bad':c.density<2?'warn':'good'}">${c.density}</span>`, c.orphans]);
  });
});
document.getElementById('p-clusters').innerHTML =
 `<p class="note">Traffic and link health by topic. Density is links per page inside a topic: under 1 means the pages sit alone.</p>`+
 table([{t:'Topic'},{t:'Pages',n:1},{t:'Clicks',n:1},{t:'Impressions',n:1},{t:'Internal links',n:1},{t:'Density',n:1},{t:'Orphans',n:1}], crows);

// BROKEN
const off = D.nodes.filter(n=>n.dead_links>0).sort((a,b)=>b.clicks-a.clicks);
document.getElementById('p-broken').innerHTML =
 `<p class="note">Links pointing at pages that no longer exist. Fix the link or restore the page.</p>`+
 table([{t:'Blog containing the broken link'},{t:'Clicks',n:1},{t:'Broken',n:1}],
  off.map(n=>[`<a href="${n.id}" target="_blank">${short(n.id)}</a>`, fmt(n.clicks), `<span class="bad">${n.dead_links}</span>`]))+
 `<h3>Pages being linked to that are gone</h3>`+
 table([{t:'URL'}], D.broken_targets.map(u=>[short(u)]));

// DEAD
document.getElementById('p-dead').innerHTML =
 `<p class="note">Pages still showing up in Google but returning an error. Redirect each to the closest live page.</p>`+
 table([{t:'URL'}], D.dead.map(u=>[`<a href="${u}" target="_blank">${short(u)}</a>`]));

// HEALTH
document.getElementById('p-health').innerHTML =
 `<p class="note">What readers actually do on blog pages, from Microsoft Clarity. Last 90 days.</p>
 <div class="wrap" style="margin-bottom:18px"><table><thead><tr><th>Metric</th><th class="num">Value</th><th>What it means</th></tr></thead><tbody>
 <tr><td><b>Average scroll depth</b></td><td class="num warn">${H.scroll.long}%</td><td style="color:var(--mut)">Most readers stop a third of the way down</td></tr>
 <tr><td>Active time on page</td><td class="num">${H.active.long}s</td><td style="color:var(--mut)">Time actually reading, not just open</td></tr>
 <tr><td>Pages per session</td><td class="num">${(+H.pps.long).toFixed(2)}</td><td style="color:var(--mut)">Close to 1: almost nobody reads a second page</td></tr>
 </tbody></table></div>
 <h3>Where readers get stuck</h3>
 <div class="wrap" style="margin-bottom:18px"><table><thead><tr><th>Signal</th><th class="num">Sessions</th><th class="num">Share</th></tr></thead>
 <tbody>${H.friction.map(f=>`<tr><td>${f.k}</td><td class="num">${f.long.n}</td><td class="num warn">${f.long.p}</td></tr>`).join('')}</tbody></table></div>
 <h3>Conversions from blog pages</h3>
 <p class="note">Every one of these fires less often than a dead click.</p>
 <div class="wrap" style="margin-bottom:18px"><table><thead><tr><th>Action</th><th class="num">Sessions</th><th class="num">Share</th></tr></thead>
 <tbody>${H.events.map(e=>`<tr><td>${e.k}</td><td class="num">${e.n}</td><td class="num">${e.p}</td></tr>`).join('')}</tbody></table></div>
 <h3>Where readers come from</h3>
 <div class="wrap"><table><thead><tr><th>Source</th><th class="num">Sessions</th></tr></thead>
 <tbody>${H.referrers.map(r=>{const ai=/chatgpt|gemini|perplexity|claude|copilot/i.test(r[0]);
 return `<tr><td>${r[0]} ${ai?'<span class="pill" style="border-color:#4d8ef7;color:#4d8ef7">AI</span>':''}</td><td class="num">${fmt(r[1])}</td></tr>`;}).join('')}</tbody></table></div>`;

// GRAPH
document.getElementById('p-graph').innerHTML =
 `<p class="note">Each dot is a blog. Bigger dot means more clicks from Google. Colour is the topic. Lines are links between blogs. Dots with a red ring have nothing linking to them.</p>
 <div class="legend" id="legend"></div><svg id="graph"></svg>`;

const legend = document.getElementById('legend');
const active = new Set(D.clusters.map(c=>c.id));
D.parents.forEach(p=>{
  const subs = D.clusters.filter(c=>c.parent===p.name);
  const g = document.createElement('div'); g.className='lgrp';
  g.innerHTML = `<div class="hd">${p.name} &middot; ${fmt(p.clicks)} clicks</div>`;
  const row = document.createElement('div'); row.style.display='flex'; row.style.flexWrap='wrap'; row.style.gap='5px';
  subs.forEach(c=>{
    const el=document.createElement('div'); el.className='lg';
    el.innerHTML=`<span class="dot" style="background:${c.colour};margin:0"></span>${c.sub} <b>${fmt(c.clicks)}</b>`;
    el.onclick=()=>{active.has(c.id)?active.delete(c.id):active.add(c.id);el.classList.toggle('off');draw();};
    row.appendChild(el);
  });
  g.appendChild(row); legend.appendChild(g);
});

const tip=document.getElementById('tip');
function draw(){
  const svg=d3.select('#graph'); svg.selectAll('*').remove();
  const W=document.getElementById('graph').clientWidth,Hh=620;
  svg.attr('viewBox',`0 0 ${W} ${Hh}`);
  const nodes=D.nodes.filter(n=>active.has(n.cluster)).map(n=>({...n}));
  const ids=new Set(nodes.map(n=>n.id));
  const links=D.edges.filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>({...e}));
  const r=n=>3+Math.sqrt(n.clicks)*0.95;
  const g=svg.append('g');
  svg.call(d3.zoom().scaleExtent([0.3,6]).on('zoom',ev=>g.attr('transform',ev.transform)));
  const L=g.append('g').attr('stroke','#ffffff').attr('stroke-opacity',.28)
    .selectAll('line').data(links).join('line').attr('stroke-width',.9)
    .attr('stroke-linecap','round');
  const N=g.append('g').selectAll('circle').data(nodes).join('circle')
    .attr('r',r).attr('fill',n=>n.colour).attr('fill-opacity',.88)
    .attr('stroke',n=>n.inbound===0?'#f5555d':'none').attr('stroke-width',n=>n.inbound===0?1.3:0)
    .style('cursor','pointer')
    .on('mousemove',(ev,n)=>{tip.style.opacity=1;tip.style.left=(ev.clientX+14)+'px';tip.style.top=(ev.clientY+14)+'px';
      tip.innerHTML=`<b>${short(n.id)}</b><br>${fmt(n.clicks)} clicks<br>${n.inbound} in &middot; ${n.outbound_blog} out<br><span style="color:${n.colour}">${n.parent} / ${n.sub}</span>`;})
    .on('mouseover',(ev,n)=>{
      L.attr('stroke-opacity',l=>(l.source.id===n.id||l.target.id===n.id)?.95:.06)
       .attr('stroke-width',l=>(l.source.id===n.id||l.target.id===n.id)?1.7:.9);})
    .on('mouseout',()=>{tip.style.opacity=0;
      L.attr('stroke-opacity',.28).attr('stroke-width',.9);})
    .on('click',(ev,n)=>window.open(n.id,'_blank'));
  const sim=d3.forceSimulation(nodes)
    .force('link',d3.forceLink(links).id(d=>d.id).distance(36).strength(.35))
    .force('charge',d3.forceManyBody().strength(-40))
    .force('center',d3.forceCenter(W/2,Hh/2))
    .force('collide',d3.forceCollide().radius(n=>r(n)+2.5))
    .on('tick',()=>{L.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
      N.attr('cx',d=>d.x).attr('cy',d=>d.y);});
  N.call(d3.drag().on('start',(e,d)=>{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;})
    .on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y;})
    .on('end',(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}));
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
  document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on'));
  t.classList.add('on'); document.getElementById('p-'+t.dataset.p).classList.add('on');
  if(t.dataset.p==='graph') draw();
});
</script></body></html>"""

out = HTML.replace("__PAYLOAD__", json.dumps(d, separators=(",", ":"))) \
          .replace("__HEALTH__", json.dumps(h, separators=(",", ":")))
open("site/link-ledger.html", "w").write(out)
print("written", round(len(out) / 1024), "kb")
