const CONFIG = window.STOCK_RADAR_CONFIG;
const state = { stocks: [], market: 'all', minScore: 0, query: '', lastGeneratedAt: null };
const $ = (id) => document.getElementById(id);

function api(path) { return `${CONFIG.apiBaseUrl}${path}`; }
function fmtNum(v, digits=2) { return Number(v).toLocaleString('ko-KR',{minimumFractionDigits:digits,maximumFractionDigits:digits}); }
function fmtMoney(v) { const eok=Math.round(Number(v)/100000000); return `${eok.toLocaleString('ko-KR')}억원`; }
function fmtTime(v) { if(!v) return '—'; return new Date(v).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}); }
function cls(v) { return Number(v)>0?'positive':Number(v)<0?'negative':''; }
function showToast(message){ const el=$('toast'); el.textContent=message; el.classList.add('show'); clearTimeout(showToast.t); showToast.t=setTimeout(()=>el.classList.remove('show'),3200); }

function sparkline(id, values, direction){
  const svg=$(id); if(!values?.length){svg.innerHTML='';return;}
  const min=Math.min(...values),max=Math.max(...values),range=max-min||1;
  const pts=values.map((v,i)=>`${(i/(values.length-1))*320},${68-((v-min)/range)*60}`).join(' ');
  const color=direction>=0?'#ff5d68':'#4e8cff';
  svg.innerHTML=`<defs><linearGradient id="g-${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".25"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs><polygon points="0,72 ${pts} 320,72" fill="url(#g-${id})"/><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>`;
}

function renderIndex(prefix, item){
  if(!item) return;
  $(`${prefix}Value`).textContent=fmtNum(item.value);
  const ch=$(`${prefix}Change`); ch.className=`index-change ${cls(item.change)}`; ch.textContent=`${item.change>0?'▲':item.change<0?'▼':'−'} ${fmtNum(Math.abs(item.change))} · ${item.change_pct>0?'+':''}${fmtNum(item.change_pct)}%`;
  $(`${prefix}Flow`).textContent=`외국인 ${fmtMoney(item.foreign_net)} · 기관 ${fmtMoney(item.institution_net)} · 개인 ${fmtMoney(item.individual_net)}`;
  sparkline(`${prefix}Chart`,item.intraday,item.change);
}

async function loadMarket(){
  if(!CONFIG.apiBaseUrl) return;
  try{const r=await fetch(api('/api/market'),{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();renderIndex('kospi',d.kospi);renderIndex('kosdaq',d.kosdaq);}catch(e){ /* retain last good values */ }
}
function renderRanking(id,items=[]){
  $(id).innerHTML=items.length?items.slice(0,5).map((s,i)=>`<li><span class="rank">${String(i+1).padStart(2,'0')}</span><div><div class="stock-name">${s.name}</div><div class="stock-meta">${s.price.toLocaleString('ko-KR')}원 <span class="${cls(s.change_pct)}">${s.change_pct>0?'+':''}${fmtNum(s.change_pct)}%</span></div></div><span class="amount">${fmtMoney(s.net_buy)}</span></li>`).join(''):'<li class="loading-row">실시간 API 연결 대기</li>';
}
async function loadInvestors(){
  if(!CONFIG.apiBaseUrl){renderRanking('foreignList');renderRanking('institutionList');return;}
  try{const r=await fetch(api('/api/investors'),{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();renderRanking('foreignList',d.foreign);renderRanking('institutionList',d.institution);$('flowUpdated').textContent=`${fmtTime(d.updated_at)} 기준`;}catch(e){renderRanking('foreignList');renderRanking('institutionList');}
}

function renderStocks(){
  const filtered=state.stocks.filter(s=>(state.market==='all'||s.market===state.market)&&s.score>=state.minScore&&(`${s.name} ${s.code}`).toLowerCase().includes(state.query));
  $('resultSummary').textContent=`${filtered.length.toLocaleString('ko-KR')}개 표시 · 총 ${state.stocks.length.toLocaleString('ko-KR')}개 종목 중`;
  $('emptyState').hidden=filtered.length>0;
  $('stockList').innerHTML=filtered.slice(0,200).map((s,i)=>`<a class="stock-row" href="https://finance.naver.com/item/main.naver?code=${s.code}" target="_blank" rel="noreferrer"><span class="score">${s.score}점</span><div><div class="stock-name">${i+1}. ${s.name}</div><div class="stock-meta">${s.code}</div></div><span class="market-tag">${s.market}</span><div class="conditions">${(s.matched||[]).map(m=>`<span class="condition">${m.label} +${m.points}</span>`).join('')}</div><span class="change ${cls(s.change_pct)}">${s.change_pct>0?'+':''}${fmtNum(s.change_pct)}%</span></a>`).join('');
}
async function loadScreening(){
  try{const r=await fetch(`${CONFIG.screeningUrl}?t=${Date.now()}`,{cache:'no-store'});if(!r.ok)throw Error();const d=await r.json();state.stocks=d.stocks||[];$('scanCount').textContent=`스캔 종목 ${Number(d.scanned_count||state.stocks.length).toLocaleString('ko-KR')}개`;$('updatedAt').textContent=`마지막 갱신 ${fmtTime(d.generated_at)}`;$('statusText').textContent=d.status==='ok'?'08:30 스크리닝 정상':'스크리닝 점검 필요';$('statusDot').className=d.status==='ok'?'ok':'error';renderStocks();if(state.lastGeneratedAt&&state.lastGeneratedAt!==d.generated_at)notify('Stock Radar 업데이트 완료',`${state.stocks.length}개 종목의 스크리닝이 완료되었습니다.`);state.lastGeneratedAt=d.generated_at;}catch(e){$('statusText').textContent='데이터를 불러오지 못했습니다';$('statusDot').className='error';$('resultSummary').textContent='results.json 연결을 확인해주세요.';}
}
async function notify(title,body){if(Notification.permission==='granted'){const reg=await navigator.serviceWorker?.ready;reg?reg.showNotification(title,{body,icon:'icon.svg'}):new Notification(title,{body});}}
async function enableNotifications(){if(!('Notification'in window)){showToast('이 브라우저는 알림을 지원하지 않습니다.');return;}const p=await Notification.requestPermission();$('notifyButton').textContent=p==='granted'?'알림 켜짐':'알림 허용 필요';showToast(p==='granted'?'업데이트 알림을 켰습니다.':'브라우저 설정에서 알림을 허용해주세요.');}

document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active');state.market=b.dataset.market;renderStocks();}));
$('scoreFilter').addEventListener('change',e=>{state.minScore=Number(e.target.value);renderStocks();});
$('searchInput').addEventListener('input',e=>{state.query=e.target.value.trim().toLowerCase();renderStocks();});
$('notifyButton').addEventListener('click',enableNotifications);
$('refreshButton').addEventListener('click',async()=>{await Promise.all([loadMarket(),loadInvestors(),loadScreening()]);showToast('최신 데이터를 확인했습니다.');});
if('serviceWorker'in navigator) navigator.serviceWorker.register('sw.js');
loadScreening();loadMarket();loadInvestors();setInterval(loadMarket,CONFIG.marketPollMs);setInterval(loadInvestors,CONFIG.investorPollMs);setInterval(loadScreening,60000);
