#!/usr/bin/env python3
"""
build_inventory_page.py - builds comic_inventory.html from a CLZ-style XML collection export.

Usage:  python3 build_inventory_page.py [export.xml] [comic_inventory.html]

With no arguments it uses the most recently modified *.xml in the current folder.
The generated page contains your whole inventory: keep it (and your XML) private.

The page: search or filter your inventory (graded and signed filters, duplicates as an expandable tree,
sortable Box column), pick a comic, and click "Fetch from eBay". With the Chrome extension in
comic_bridge_extension/ loaded, the eBay Product Research results you open arrive in the bottom panel with
photos; you untick wrong covers/lots and save the median. "Export CSV" downloads every saved value.
"""
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print(__doc__)
    sys.exit(0)
if len(sys.argv) > 1:
    xml_path = sys.argv[1]
else:
    found = sorted(glob.glob("*.xml"), key=os.path.getmtime, reverse=True)
    if not found:
        sys.exit("No XML file given and none found in this folder.\n" + __doc__)
    xml_path = found[0]
    print(f"Using {xml_path}")
out_path = sys.argv[2] if len(sys.argv) > 2 else "comic_inventory.html"


def t(c, path, default=""):
    e = c.find(path)
    return e.text.strip() if e is not None and e.text else default


rows = []
for c in ET.parse(xml_path).getroot().findall(".//comic"):
    series = t(c, ".//mainsection/series/displayname", "N/A")
    issue = t(c, "issuenr")
    ext = t(c, "issueext")
    issue = issue.replace(ext, "") if ext else issue
    slab_el = c.find("isslabbed")
    slabbed = slab_el is not None and slab_el.get("boolvalue") == "1"
    gd, grader_raw = t(c, ".//grade/displayname"), t(c, ".//gradingcompany/displayname")
    grader = grader_raw or "CGC"
    grade = f"{grader} {gd.split()[0]}" if slabbed and gd else (gd if gd and gd != "0.0" else "Raw")
    key_el = c.find("iskeycomic")
    lid = key_el.get("listid", "0") if key_el is not None else "0"
    key = "MAJOR KEY" if lid == "2" else ("KEY" if lid not in ("0", "") and (key_el.text or "").strip().lower() not in ("no", "") else "")
    kw = " ".join(x for x in (series if series != "N/A" else "", f"#{issue}" if issue else "",
                              grade if slabbed else "") if x)
    try:
        q = int(t(c, "quantity", "1") or 1)
    except ValueError:
        q = 1
    rows.append({"s": series, "i": issue, "v": t(c, ".//edition/displayname"), "g": grade,
                 "sl": 1 if slabbed else 0, "ky": key, "kr": t(c, "keycomicreason"), "q": q,
                 "st": t(c, ".//location/displayname"), "c": t(c, "coverfrontdefault"), "kw": kw,
                 "gr": (grader_raw or "Other graded") if slabbed else "",
                 "sg": ", ".join(x.text.strip() for x in c.findall(".//signees/signee/displayname") if x.text)})

TEMPLATE = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Comic Inventory + eBay Sold Data</title>
<style>
:root{--bg:#fff;--fg:#1c1c1c;--mut:#666;--line:#d9d9d9;--card:#f4f4f4;--acc:#0b63ce;--ok:#1a7f37;--bad:#b42318}
@media(prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#9a9a9a;--line:#333;--card:#222;--acc:#6cb2ff;--ok:#56d364;--bad:#ff8a80}}
*{box-sizing:border-box}body{margin:0;font:14px -apple-system,Arial,sans-serif;background:var(--bg);color:var(--fg)}
header{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
input,select,button,textarea{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px}
button{cursor:pointer}button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}
#q{flex:1;min-width:200px}.mut{color:var(--mut);font-size:12px}
main{display:grid;grid-template-columns:minmax(330px,50%) 1fr;gap:14px;padding:14px}
@media(max-width:800px){main{grid-template-columns:1fr}}
#list{max-height:42vh;overflow:auto;border:1px solid var(--line);border-radius:8px}
.it{padding:7px 10px;border-bottom:1px solid var(--line);cursor:pointer}.it:hover,.it.on{background:var(--card)}
.it .ok{color:var(--ok);font-weight:600;margin-left:6px}
.row{display:grid;grid-template-columns:1fr 84px 40px;gap:6px;align-items:start}
.lh{position:sticky;top:0;z-index:2;background:var(--card);padding:6px 10px;border-bottom:1px solid var(--line);font-size:12px;font-weight:600}
.lh span{cursor:pointer;user-select:none}.lh span:hover{color:var(--acc)}.bx,.qy{font-size:12px;color:var(--mut)}
#exthelp{padding:8px 14px;border-bottom:1px solid var(--line);font-size:12px;line-height:1.6}#ext{cursor:pointer}
#detail{display:flex;gap:14px;align-items:flex-start}#detail img{width:130px;border-radius:4px;border:1px solid var(--line)}
.badge{display:inline-block;padding:1px 6px;border-radius:4px;font-size:11px;background:var(--card);border:1px solid var(--line);margin-right:4px}
.links a{display:inline-block;margin:4px 6px 0 0;padding:5px 10px;border:1px solid var(--acc);border-radius:6px;color:var(--acc);text-decoration:none;cursor:pointer}
.chip{border-radius:16px;padding:3px 11px}.chip.on{background:var(--acc);color:#fff;border-color:var(--acc)}.chip .mut{color:inherit;opacity:.75}
#chips{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
.caret{display:inline-block;width:16px;color:var(--mut);cursor:pointer}.badge.dup{background:var(--acc);color:#fff;border-color:var(--acc)}
.kid{padding:4px 10px 4px 26px;border-bottom:1px solid var(--line);font-size:12px;color:var(--mut);cursor:pointer}.kid:hover{background:var(--card)}
.res td{vertical-align:top}.res img{width:92px;height:auto;display:block;border-radius:3px;border:1px solid var(--line)}
.res a{color:var(--acc)}.res .why{background:#b4231833;border-color:var(--bad);color:var(--bad)}
.stat img{width:70px;display:block;margin-top:4px;border-radius:3px;border:1px solid var(--line)}
details summary{cursor:pointer;margin:6px 0}
section{padding:0 14px 30px}h2{font-size:16px;margin:8px 0}
textarea{width:100%;height:110px;font-family:ui-monospace,monospace;font-size:12px}
table{border-collapse:collapse;width:100%;margin-top:8px}th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;font-size:13px}
td.p{text-align:right;font-variant-numeric:tabular-nums}tr.x td{opacity:.4;text-decoration:line-through}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 14px}
.stat b{display:block;font-size:18px}
</style></head><body>
<header><input id="q" placeholder="Search series, issue, variant..." autofocus>
<select id="f"><option value="">All books</option><option value="key">Key issues</option>
<option value="todo">Not valued yet</option><option value="done">Valued</option></select>
<span class="mut" id="cnt"></span><span class="mut" id="ext"></span><span id="tot" class="mut"></span><button onclick="exportCsv()">Export CSV</button></header>
<div id="exthelp" class="mut" hidden><b>Extension setup</b> (only needed for the automatic Fetch; copy/paste always works): 1) In Chrome open <code>chrome://extensions</code> and switch on <b>Developer mode</b> (top right). 2) Click <b>Load unpacked</b> and choose the folder that directly contains <code>manifest.json</code> (comic_bridge_extension). 3) Check its switch is on and there is no red <b>Errors</b> button. 4) Reload this tab and the eBay tab. Open this page at <code>localhost:8765</code> or <code>127.0.0.1:8765</code>.</div>
<main><div><div id="chips"></div><div id="list"></div></div><div id="detail"><span class="mut">Pick a comic from the list.</span></div></main>
<section id="ebay" hidden><h2>eBay sold data</h2>
<div class="mut">With the Chrome extension: click Fetch from eBay above; the results arrive here by themselves. Without it: open a manual Research link, press Ctrl/Cmd+A then Ctrl/Cmd+C on the results and paste here. Untick rows that are the wrong cover, grade, or a lot.</div>
<div class="mut" id="stat"></div>
<details id="rawd" open><summary class="mut">Raw text (manual paste goes here)</summary><textarea id="paste" placeholder="Paste the copied eBay results here..."></textarea></details>
<div id="out"></div></section>
<script>
const DATA=__DATA__;
const $=id=>document.getElementById(id),LS='comicVals_v1';
let saved={};try{saved=JSON.parse(localStorage.getItem(LS)||'{}')}catch(e){}
const persist=()=>{try{localStorage.setItem(LS,JSON.stringify(saved))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const money=n=>'$'+Number(n).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const M=new Map();
for(const b of DATA){const id=[b.s,b.i,b.v,b.g].join('|'),e={q:b.q,st:b.st,sg:b.sg},x=M.get(id);
 if(x){x.q+=b.q;x.ents.push(e);if(b.st&&!x.st.includes(b.st))x.st.push(b.st)}else M.set(id,{...b,id,st:b.st?[b.st]:[],ents:[e]})}
const ALL=[...M.values()].sort((a,b)=>a.s.localeCompare(b.s)||(parseInt(a.i)||0)-(parseInt(b.i)||0));
const rk=x=>x===''||x==null?2:(isNaN(parseFloat(x))?1:0);   // 0 = numeric box, 1 = text box (e.g. A7), 2 = no box
const natural=(a,c)=>{const ra=rk(a),rc=rk(c);if(ra!==rc)return ra-rc;if(ra===0&&parseFloat(a)!==parseFloat(c))return parseFloat(a)<parseFloat(c)?-1:1;return String(a).localeCompare(String(c))};
ALL.forEach((b,i)=>{b.ix=i;b.st.sort(natural);b.ents.sort((x,y)=>natural(x.st,y.st));b.signed=b.ents.some(e=>e.sg);
 b.hay=[b.s,b.i,b.v,b.g,b.st.join(' '),b.ents.map(e=>e.sg).join(' ')].join(' ').toLowerCase()});
let sel=null,parsed=[];
const OPEN=new Set(),GR=[...new Set(ALL.filter(b=>b.sl).map(b=>b.gr))].sort(),CH=['Raw',...GR,'Signed'],ON={Raw:true};
const CNT={};for(const k of CH)CNT[k]=ALL.filter(b=>k==='Signed'?b.signed:k==='Raw'?!b.sl:b.sl&&b.gr===k).length;
const typeOk=b=>b.sl?!!ON[b.gr]:!!ON.Raw;
const who=b=>[...new Set(b.ents.map(e=>e.sg).filter(Boolean))].join('; ');
const copyLine=e=>'&#128230; '+esc(e.st||'no location')+(e.q>1?' &times;'+e.q:'')+(e.sg?' &#9997; '+esc(e.sg):'');
function renderChips(){$('chips').innerHTML=CH.map(k=>`<button class="chip${ON[k]?' on':''}" data-k="${esc(k)}">${esc(k)} <span class="mut">${CNT[k]}</span></button>`).join('')+'<span class="mut" id="hint"></span>'}
$('chips').onclick=e=>{const c=e.target.closest('.chip');if(!c)return;ON[c.dataset.k]=!ON[c.dataset.k];renderChips();renderList(true)};

let shown=200,VN=0;const SORT={k:'title',d:1};
const AR=k=>SORT.k===k?(SORT.d>0?' &#9650;':' &#9660;'):'';
const boxCmp=(a,b)=>{const x=a.ents[0].st,y=b.ents[0].st,rx=rk(x),ry=rk(y);
 if(rx!==ry)return rx-ry;   // numbers, then text boxes, then no box: never reversed
 return natural(x,y)*SORT.d||(a.ix-b.ix)*SORT.d};
const CMP={title:(a,b)=>(a.ix-b.ix)*SORT.d,box:boxCmp,qty:(a,b)=>(a.q-b.q||a.ix-b.ix)*SORT.d};
const boxTxt=b=>b.st.length?esc(b.st.slice(0,3).join(', '))+(b.st.length>3?'&hellip;':''):'&mdash;';
const ttl=b=>esc(b.s)+(b.i?' #'+esc(b.i):'');
function renderList(reset){
 if(reset===true)shown=200;
 const q=$('q').value.toLowerCase().trim(),f=$('f').value,V=[];let cp=0,hid=0;
 for(const b of ALL){
  if(f==='key'&&!b.ky||f==='todo'&&saved[b.id]||f==='done'&&!saved[b.id])continue;
  if(q&&!b.hay.includes(q))continue;
  if(ON.Signed&&!b.signed)continue;
  if(!typeOk(b)){if(b.sl&&ON.Signed)hid++;continue}
  V.push(b);cp+=b.q}
 if(SORT.k!=='title'||SORT.d<0)V.sort(CMP[SORT.k]);
 VN=V.length;$('cnt').textContent=VN+' books, '+cp+' copies';
 $('list').innerHTML='<div class="lh row"><span data-sort="title">Comic'+AR('title')+'</span><span data-sort="box">Box'+AR('box')+'</span><span data-sort="qty">Qty'+AR('qty')+'</span></div>'+
  V.slice(0,shown).map(b=>{const dup=b.q>1,op=OPEN.has(b.id);
  return `<div class="it row${sel&&sel.id===b.id?' on':''}" data-id="${esc(b.id)}"><div><span class="caret"${dup?' data-t="'+esc(b.id)+'"':''}>${dup?(op?'&#9662;':'&#9656;'):''}</span>${ttl(b)}${b.signed?' &#9997;':''}${dup?' <span class="badge dup">x'+b.q+'</span>':''}${saved[b.id]?'<span class="ok">'+money(saved[b.id].med)+'</span>':''}<div class="mut" style="margin-left:16px">${esc(b.v||'')} ${b.sl?'['+esc(b.g)+']':''}</div></div><div class="bx">${boxTxt(b)}</div><div class="qy">${b.q}</div></div>`+
  (dup&&op?b.ents.map(e=>`<div class="kid row" data-id="${esc(b.id)}"><div>&#9492; ${e.sg?'&#9997; '+esc(e.sg):'copy'}</div><div class="bx">${esc(e.st||'\u2014')}</div><div class="qy">${e.q}</div></div>`).join(''):'')}).join('');
 $('hint').textContent=hid?' '+hid+' signed graded book'+(hid>1?'s':'')+' hidden - turn on CGC/CBCS above':'';
 let t=0;for(const b of ALL)if(saved[b.id])t+=saved[b.id].med*b.q;$('tot').textContent=' | saved total: '+money(t);
}
$('list').onclick=e=>{const h=e.target.closest('[data-sort]');
 if(h){const k=h.dataset.sort;if(SORT.k===k)SORT.d*=-1;else{SORT.k=k;SORT.d=1}renderList(true);return}
 const c=e.target.closest('.caret');
 if(c&&c.dataset.t){OPEN.has(c.dataset.t)?OPEN.delete(c.dataset.t):OPEN.add(c.dataset.t);renderList();return}
 const d=e.target.closest('[data-id]');if(d)select(M.get(d.dataset.id))};
$('q').oninput=$('f').onchange=()=>renderList(true);
$('list').onscroll=()=>{const l=$('list');if(shown<VN&&l.scrollTop+l.clientHeight>=l.scrollHeight-250){const t=l.scrollTop;shown+=300;renderList();l.scrollTop=t}};

const CAT=259104;  // eBay category: Comics & Graphic Novels
const TZ=(()=>{try{return Intl.DateTimeFormat().resolvedOptions().timeZone||'America/Los_Angeles'}catch(e){return 'America/Los_Angeles'}})();
const rUrl=(kw,d)=>{const e=Date.now();return 'https://www.ebay.com/sh/research?marketplace=EBAY-US&keywords='+encodeURIComponent(kw).replace(/%20/g,'+')+'&dayRange='+d+'&endDate='+e+'&startDate='+(e-d*864e5)+'&categoryId='+CAT+'&offset=0&limit=50&sorting=-datelastsold&tabName=SOLD&tz='+encodeURIComponent(TZ)};
const sUrl=kw=>'https://www.ebay.com/sch/63/i.html?_nkw='+encodeURIComponent(kw).replace(/%20/g,'+')+'&LH_Sold=1&LH_Complete=1&_sop=13';
const open_=u=>window.open(u,'_blank'),openFetch=u=>{$('stat').innerHTML=extOk?'Waiting for results from eBay... (the eBay tab will close itself when they arrive)':'<b style="color:var(--bad)">Extension not connected, so nothing will arrive here by itself.</b> On the eBay tab press Cmd/Ctrl+A then Cmd/Ctrl+C, come back, and paste below. (Fix: click the red Extension badge at the top for setup.)';window.open(u,'ci_fetch')};

function select(b){
 sel=b;parsed=[];$('paste').value='';
 $('detail').innerHTML=(b.c?`<img src="${esc(b.c)}" referrerpolicy="no-referrer" alt="cover">`:'')+
 `<div><b style="font-size:16px">${ttl(b)}</b><div>${esc(b.v||'')}</div>
 <div style="margin:6px 0"><span class="badge">${esc(b.g)}</span>${b.ky?'<span class="badge">&#128273; '+esc(b.ky)+'</span>':''}${b.signed?'<span class="badge">&#9997; '+esc(who(b))+'</span>':''}<span class="badge">qty ${b.q}</span></div>
 ${b.q>1||b.st.length?'<div class="mut" style="margin-bottom:4px">Copies: '+b.ents.map(copyLine).join(' &middot; ')+'</div>':''}
 ${b.kr?'<div class="mut">'+esc(b.kr)+'</div>':''}<div class="mut">Search: ${esc(b.kw)}</div>
 <div class="links"><a style="background:var(--acc);color:#fff" onclick="openFetch(rUrl(sel.kw,90)+'#ci')">Fetch from eBay (90d)</a><a onclick="openFetch(rUrl(sel.kw,365)+'#ci')">Fetch (1y)</a><a onclick="open_(rUrl(sel.kw,90))">Research 90d (manual)</a><a onclick="open_(sUrl(sel.kw+' '+(sel.v||'').replace(/\\b(regular|edition|cover)\\b/gi,'').trim()))">Public sold page</a></div></div>`;
 $('ebay').hidden=false;renderOut();renderList();
}

const DATE=/[A-Z][a-z]{2,8}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}\/\d{1,2}\/\d{2,4}|\d{4}-\d{2}-\d{2}/;
const PRICE=/\$\s?([\d,]+(?:\.\d{1,2})?)/,num=s=>parseFloat(s.replace(/,/g,''));
const MARKG=/,?\s*preview full size image/ig,NOISE=/^(edit|skip to main content|view similar|[\u2014\u2013-]|n\/a)$/i,FMT=/fixed price|auction|best offer|buy it now/i;
const isPrice=s=>/^\$\s?[\d,]+(\.\d{1,2})?$/.test(s);
function parseRec(txt){
 const L=txt.split(/\r?\n/).map(s=>s.replace(MARKG,'').trim()).filter(Boolean);
 let t='';
 for(const s of L){if(NOISE.test(s)||isPrice(s)||/^\d{1,4}$/.test(s)||(DATE.test(s)&&s.length<20)||/^(\d+% )?free shipping$/i.test(s)||/^(fixed price|auction|best offer|buy it now)$/i.test(s))continue;if(s.length>=4){t=s;break}}
 if(!t)return null;
 let p=null,ship=null,fmt='',d='';const ints=[];
 for(let j=0;j<L.length;j++){const s=L[j];
  if(isPrice(s)){const nx=L[j+1]||'';
   if(/shipping/i.test(nx)){if(ship==null)ship=num(s.replace('$',''))}
   else if(FMT.test(nx)){if(p==null){p=num(s.replace('$',''));fmt=nx}}}
  else if(/^\d{1,4}$/.test(s))ints.push(+s);
  else if(!d){const m=DATE.exec(s);if(m&&s.length<24)d=m[0]}}
 if(p==null){const f=L.find((s,j)=>isPrice(s)&&!/shipping/i.test(L[j+1]||''));if(f)p=num(f.replace('$',''))}
 return p==null?null:{t,p,ship,d,fmt,n:ints[0]||1,x:false,auto:true}}
const LOT=/\b(lot|lots|bundle|set|run|complete|collection|bulk|pick|choose|pack)\b|#?\d+\s*[-\u2013]\s*#?\d+/i;
const reEsc=x=>x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
function flag(r){
 if(!sel)return '';
 if(LOT.test(r.t))return 'lot/set?';
 if(sel.i&&!(new RegExp('(?:#\\s*|\\bno\\.?\\s*)'+reEsc(sel.i)+'(?!\\d)','i').test(r.t)||new RegExp('(?<![\\d.$])'+reEsc(sel.i)+'(?![\\d.])').test(r.t)))return 'other issue?';
 const g=/\b(CGC|CBCS|PGX)\b/i.test(r.t);
 if(sel.sl&&!g)return 'not graded?';
 if(!sel.sl&&g)return 'graded?';
 return ''}
function applyFlags(){for(const r of parsed)if(r.auto){const w=flag(r);if(w){r.x=true;r.why=w}}}
const big=u=>u?u.replace(/s-l\d+(\.\w+)$/,'s-l300$1'):'';
function parsePaste(t){
 if(/preview full size image/i.test(t)){const recs=t.split(MARKG).slice(1).map(parseRec).filter(Boolean);if(recs.length)return recs}
 const lines=t.split(/\r?\n/).map(l=>l.trim()).filter(Boolean);if(!lines.length)return[];
 const hi=lines.findIndex(l=>l.includes('\t')&&/sold/i.test(l)&&/price/i.test(l));
 if(hi>=0){ // header row found: use column names
  const H=lines[hi].split('\t').map(h=>h.trim().toLowerCase()),ix=re=>H.findIndex(h=>re.test(h));
  const ti=ix(/title|item|listing/),pi=ix(/avg.*sold|sold.*price|^price/),di=ix(/date/),out=[];
  if(pi>=0){for(const l of lines.slice(hi+1)){const c=l.split('\t').map(x=>x.trim()),pm=PRICE.exec(c[pi]||'');
   if(pm)out.push({t:c[ti>=0?ti:0]||'',p:num(pm[1]),d:(c[di]||''),x:false})}
   if(out.length)return out}}
 const out=[];let cur={t:'',p:null,d:''};
 const flush=()=>{if(cur.p!=null)out.push({...cur,x:false});cur={t:'',p:null,d:''}};
 for(const l of lines)for(const c of l.split('\t').map(s=>s.trim()).filter(Boolean)){
  const pm=PRICE.exec(c),dm=DATE.exec(c);
  if(pm&&c.length<20){if(cur.p==null)cur.p=num(pm[1]);continue}
  if(dm&&c.length<30){if(!cur.d)cur.d=dm[0];continue}
  if(c.length>=15&&!pm){if(cur.p!=null)flush();if(!cur.t)cur.t=c}}
 flush();return out}
function stats(a){const p=a.filter(r=>!r.x).map(r=>r.p).sort((x,y)=>x-y);if(!p.length)return null;const m=p.length>>1;
 return{n:p.length,low:p[0],high:p[p.length-1],avg:p.reduce((s,v)=>s+v,0)/p.length,med:p.length%2?p[m]:(p[m-1]+p[m])/2}}

$('paste').oninput=()=>{parsed=parsePaste($('paste').value);applyFlags();renderOut()};
function toggle(i){parsed[i].x=!parsed[i].x;renderOut()}
function renderOut(){
 let h='';const s=stats(parsed),sv=sel&&saved[sel.id];
 if(sv)h+=`<div class="mut">Saved for this book: median ${money(sv.med)} from ${sv.n} sales on ${esc(sv.at)} <a href="#" onclick="del();return false">remove</a></div>`;
 if($('paste').value.trim()&&!parsed.length)h+='<p style="color:var(--bad)">Could not find prices in that text. Copy the results table again, or send me a sample so I can tune the parser.</p>';
 if(parsed.length){
  const cov=sel&&sel.c?`<div class="stat"><span class="mut">Your cover</span><img src="${esc(sel.c)}" referrerpolicy="no-referrer" alt=""></div>`:'';
  h+=s?`<div class="stats">${cov}<div class="stat"><span class="mut">Sales used</span><b>${s.n}/${parsed.length}</b></div><div class="stat"><span class="mut">Median</span><b>${money(s.med)}</b></div><div class="stat"><span class="mut">Average</span><b>${money(s.avg)}</b></div><div class="stat"><span class="mut">Low</span><b>${money(s.low)}</b></div><div class="stat"><span class="mut">High</span><b>${money(s.high)}</b></div></div><button class="pri" onclick="save()">Save median ${money(s.med)} to this comic</button>`:`<div class="stats">${cov}</div><p class="mut">All rows unticked.</p>`;
  h+='<div class="mut" style="margin-top:6px">Rows that look like a lot/set, another issue or the wrong grade start unticked (tick them back if they are right).</div>';
  h+='<table class="res"><tr><th>Use</th><th>Photo</th><th>Listing</th><th>Sold</th><th style="text-align:right">Price</th></tr>'+parsed.map((r,i)=>{
   const href=r.url||big(r.img),ti=r.url?`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.t)}</a>`:esc(r.t);
   return `<tr class="${r.x?'x':''}"><td><input type="checkbox" ${r.x?'':'checked'} onchange="toggle(${i})"></td><td>${r.img?`<a href="${esc(href)}" target="_blank" rel="noopener"><img src="${esc(big(r.img))}" referrerpolicy="no-referrer" loading="lazy" alt=""></a>`:''}</td><td>${ti}${r.why?' <span class="badge why">'+esc(r.why)+'</span>':''}<div class="mut">${esc(r.fmt||'')}${r.n>1?' &middot; '+r.n+' sold':''}${r.ship!=null?' &middot; shipping '+money(r.ship):''}</div></td><td>${esc(r.d)}</td><td class="p">${money(r.p)}</td></tr>`}).join('')+'</table>'}
 $('out').innerHTML=h}
function save(){const s=stats(parsed);if(!s||!sel)return;saved[sel.id]={n:s.n,med:+s.med.toFixed(2),avg:+s.avg.toFixed(2),low:s.low,high:s.high,at:new Date().toISOString().slice(0,10)};persist();renderOut();renderList()}
function del(){delete saved[sel.id];persist();renderOut();renderList()}
function exportCsv(){const R=[['Series','Issue','Variant','Grade','Qty','Storage','Sales used','Median','Average','Low','High','Saved','Line total (median x qty)']];
 for(const b of ALL){const s=saved[b.id];if(s)R.push([b.s,b.i,b.v,b.g,b.q,b.st.join('; '),s.n,s.med,s.avg,s.low,s.high,s.at,(s.med*b.q).toFixed(2)])}
 const csv=R.map(r=>r.map(x=>'"'+String(x).replace(/"/g,'""')+'"').join(',')).join('\n'),a=document.createElement('a');
 a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='comic_values_'+new Date().toISOString().slice(0,10)+'.csv';a.click()}
// Receives data from the optional Chrome extension (see comic_bridge_extension)
window.addEventListener('message',e=>{const d=e.data;if(e.source!==window||!d||d.type!=='EBAY_DATA')return;
 if(!sel){alert('Pick a comic in the list first, then send the eBay data.');return}
 $('paste').value=d.text||'';
 const R=d.rows||[],tr=parsePaste(d.text||'');
 let recs=R.map(r=>{const x=parseRec(r.text||'');return x&&{...x,img:r.img||'',url:r.url||''}}).filter(Boolean);
 if(recs.length&&recs.length>=tr.length*0.8)parsed=recs;
 else{parsed=tr;if(R.length&&R.length===tr.length)tr.forEach((r,i)=>{r.img=R[i].img||'';r.url=R[i].url||''})}
 applyFlags();
 const ph=parsed.filter(r=>r.img).length;
 $('stat').textContent='Received '+parsed.length+' sales ('+(d.text||'').length.toLocaleString()+' characters) from eBay at '+new Date().toLocaleTimeString()+' | extension '+(d.v?'v'+d.v:'(version unknown, older than 1.6)')+' read '+R.length+' listing rows, '+ph+' photos';
 try{$('rawd').open=false}catch(_){}
 renderOut();
 if(d.kw&&d.kw!==sel.kw)$('out').insertAdjacentHTML('afterbegin','<p style="color:var(--bad)">Heads up: this eBay data was for "'+esc(d.kw)+'" but "'+esc(sel.kw)+'" is selected.</p>');
 $('ebay').scrollIntoView()});
let extOk=false;
const setExt=()=>{const el=$('ext');el.textContent=extOk?' | Extension: connected':(typeof location!=='undefined'&&location.protocol==='file:'?' | Extension: open via http://localhost:8765, not the file':' | Extension: not detected (click for setup)');el.style.color=extOk?'var(--ok)':'var(--bad)';$('exthelp').hidden=extOk};
$('ext').onclick=()=>{$('exthelp').hidden=!$('exthelp').hidden};
window.addEventListener('message',e=>{if(e.source===window&&e.data&&e.data.type==='CI_EXT_READY'){extOk=true;setExt()}});
window.postMessage({type:'CI_PING'},'*');setTimeout(setExt,1500);
renderChips();renderList();
</script></body></html>"""

data = json.dumps(rows, separators=(",", ":")).replace("</", "<\\/")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(TEMPLATE.replace("__DATA__", data))
print(f"Wrote {len(rows)} comics to {out_path}")
