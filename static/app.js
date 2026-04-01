// NOTE: Live mic is server-side PyAudio. On VPS without audio hardware,
// mic capture is non-functional. Browser-based WebRTC mic is Phase N+1 scope.

// ── Socket & DOM ──────────────────────────────────────────────────────────────
const socket = io();
const tr     = document.getElementById('tr');
const ai     = document.getElementById('ai');
let words = 0, einwaende = 0, analysen = 0;
let interim = null;
let paused  = false;

// ── Session-Timer ─────────────────────────────────────────────────────────────
let sessionTimer   = null;
let sessionSeconds = 0;

function startSessionTimer(){
  if (sessionTimer) return;
  sessionTimer = setInterval(()=>{
    sessionSeconds++;
    const ts = String(Math.floor(sessionSeconds/60)).padStart(2,'0') + ':' +
               String(sessionSeconds % 60).padStart(2,'0');
    const el  = document.getElementById('session-timer');
    if (el) el.textContent = ts;
    const kp  = document.getElementById('kp-timer');
    if (kp) kp.textContent = ts;
  }, 1000);
}
function stopSessionTimer(){
  if (sessionTimer){ clearInterval(sessionTimer); sessionTimer = null; sessionSeconds = 0; }
  const el = document.getElementById('session-timer');
  if (el) el.textContent = '00:00';
  const kp = document.getElementById('kp-timer');
  if (kp) kp.textContent = '00:00';
}

// ── Sprachanalyse (client-side, nur für lokales Word-Count) ───────────────────
const speech = {
  beraterWords: 0, kundeWords: 0,
  beraterSegments: 0,
  startTime: null,
};

// ── Sprachanalyse: Kreismetriken (server-driven) ─────────────────────────────
const MC_COLORS = {green:'#E8B040', amber:'#f0a500', red:'#e05c5c'};
function mcColor(key, val){
  const thresholds = {
    redeanteil: [[0,40,'green'],[40,65,'amber'],[65,999,'red']],
    tempo:      [[0,140,'green'],[140,180,'amber'],[180,999,'red']],
    monolog:    [[0,25,'green'],[25,40,'amber'],[40,999,'red']],
  };
  for (const [lo,hi,cls] of (thresholds[key]||[])){
    if (val>=lo && val<hi) return MC_COLORS[cls];
  }
  return MC_COLORS.green;
}
function updateSpeechCircles(stats){
  if (!stats) return;
  [['redeanteil','%'],['tempo',''],['monolog','s']].forEach(([key,unit])=>{
    const val = stats[key];
    if (val === undefined) return;
    const el  = document.getElementById('mc-'+key);
    const vEl = document.getElementById('mc-v-'+key);
    if (!el || !vEl) return;
    vEl.textContent  = val + unit;
    const col = mcColor(key, val);
    el.style.borderColor = col;
    el.style.color       = col;
  });
}

function updateSpeechUI() { /* kept for compatibility */ }

// ── Sprecher-Label ────────────────────────────────────────────────────────────
function spLabel(sp) {
  return sp === 0 ? 'Berater' : (sp === 1 ? 'Kunde' : '?');
}

// ── Role flip ─────────────────────────────────────────────────────────────────
async function flipRowRole(btn) {
  const el       = btn.closest('.msg');
  const isSp0    = el.classList.contains('sp0');
  const lineId   = el.dataset.lineId;
  const text     = el.dataset.text;
  const vonRolle = isSp0 ? 'Berater' : 'Kunde';
  const nachRolle= isSp0 ? 'Kunde'   : 'Berater';
  el.classList.toggle('sp0', !isSp0);
  el.classList.toggle('sp1',  isSp0);
  const tag = el.querySelector('.speaker-tag');
  if (tag) tag.textContent = nachRolle;
  fetch('/api/log_correction',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({type:'korrektur',von:vonRolle,nach:nachRolle,line_id:lineId})
  }).catch(e=>console.error('[LOG_KORR]',e));
  if (isSp0) {
    btn.disabled=true; btn.textContent='…';
    try {
      const res=await fetch('/api/analyse_line',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text,line_id:lineId})
      });
      const data=await res.json();
      if(data.ergebnis) zeigeKarte(data.ergebnis,lineId);
    } catch(e){console.error('[FLIP→Kunde]',e);}
    finally{btn.disabled=false;btn.textContent='⇄';}
  } else {
    const card=ai.querySelector(`[data-line-id="${lineId}"]`);
    if(card){
      const typEl=card.querySelector('.einwand-typ');
      const einwandTyp=typEl?typEl.textContent.trim():'';
      if(einwandTyp&&einwandTyp!=='Kein Einwand'&&einwandTyp!=='Zurückgezogen'){
        fetch('/api/log_correction',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({type:'zurueckgezogen',einwand_typ:einwandTyp,line_id:lineId})
        }).catch(e=>console.error('[LOG_ZURUCK]',e));
      }
      card.classList.add('withdrawn');
      if(typEl){typEl.textContent='Zurückgezogen';typEl.className='einwand-typ typ-kein';}
    }
  }
}

// ── Socket events ─────────────────────────────────────────────────────────────
socket.on('connect',()=>{
  document.getElementById('st').textContent='Mikrofon aktiv';
  const kpSt=document.getElementById('kp-st');
  if(kpSt) kpSt.textContent='Mikrofon aktiv';
  const kpDot=document.getElementById('kp-dot');
  if(kpDot){kpDot.classList.remove('paused');}
  // DSGVO-Banner beim Verbindungsaufbau einblenden (vor Mikrofon-Zugriff) — DSGVO-konform
  const dsgvoBanner = document.getElementById('dsgvoBanner');
  if (dsgvoBanner && !dsgvoBanner._shown) {
    dsgvoBanner._shown = true;
    dsgvoBanner.classList.add('visible');
    setTimeout(() => dsgvoBanner.classList.remove('visible'), 6000);
  }
  // Start session timer on connect — not on first transcript
  startSessionTimer();
});

socket.on('transcript', d => {
  if (d.type==='interim') {
    if(!interim){interim=document.createElement('div');interim.className='msg interim';tr.appendChild(interim);}
    interim.textContent=d.text;
  } else if (d.type==='final' && d.text.trim()) {
    if (!sessionTimer) startSessionTimer(); // fallback if connect fired before timer init
    if(interim){interim.remove();interim=null;}
    const el=document.createElement('div');
    const sp=(d.speaker===0||d.speaker===1)?d.speaker:null;
    el.className='msg final'+(sp!==null?' sp'+sp:'');
    el.dataset.lineId=d.line_id||'';
    el.dataset.text=d.text;
    const hdr=document.createElement('div');hdr.className='row-header';
    const labelTag=document.createElement('span');labelTag.className='speaker-tag';
    labelTag.textContent=sp!==null?spLabel(sp):'';
    const swapBtn=document.createElement('button');swapBtn.className='row-swap-btn';
    swapBtn.title='Rolle korrigieren';swapBtn.textContent='⇄';
    swapBtn.setAttribute('onclick','flipRowRole(this)');
    hdr.appendChild(labelTag);hdr.appendChild(swapBtn);
    el.appendChild(hdr);
    const txt=document.createElement('span');txt.textContent=d.text;
    el.appendChild(txt);
    tr.appendChild(el);

    // Sprachanalyse updaten
    const wc=d.text.trim().split(/\s+/).length;
    if(!speech.startTime) speech.startTime=Date.now();
    if(sp===0){
      speech.beraterWords+=wc; speech.beraterSegments++;
    } else if(sp===1){
      speech.kundeWords+=wc; speech.beraterSegments=0;
    }
    words+=wc;
    document.getElementById('wc').textContent=words;
    updateSpeechUI();
  }
  tr.scrollTop=tr.scrollHeight;
  recentSegments.push({speaker:sp===0?'Berater':(sp===1?'Kunde':'?'),text:d.text||''});
  if(recentSegments.length>10) recentSegments.shift();
});

// letzte Segmente für "Frage stellen" Kontext
const recentSegments = [];

// ── Coaching Panel ────────────────────────────────────────────────────────────
const coachingScroll=document.getElementById('coaching-scroll');
const katLabel={frage:'Frage fehlt',signal:'Kaufsignal',redeanteil:'Redeanteil',uebergang:'Übergang',lob:'Lob'};
const tipCards=[];

function voigeTipp(card){
  coachingScroll.appendChild(card);
  tipCards.push(card);
  if(tipCards.length>2){
    const oldest=tipCards.shift();
    oldest.classList.add('removing');
    setTimeout(()=>{if(oldest.parentNode)oldest.remove();},380);
  }
}

socket.on('coaching',d=>{
  let added=false;
  if(d.painpoint){
    const card=document.createElement('div');card.className='coaching-card painpoint';
    card.innerHTML=`<div class="coaching-top"><span class="coaching-badge badge-pain">📍 Painpoint</span><span class="coaching-time">${escHtml(d.ts)}</span></div><div class="coaching-text">${escHtml(d.painpoint)}</div>`;
    coachingScroll.appendChild(card);added=true;
  }
  if(d.tipp){
    const kat=d.kategorie||'frage';const lbl=katLabel[kat]||'Tipp';
    const card=document.createElement('div');card.className='coaching-card tip';
    card.innerHTML=`<div class="coaching-top"><span class="coaching-badge badge-${escHtml(kat)}">${escHtml(lbl)}</span><span class="coaching-time">${escHtml(d.ts)}</span></div><div class="coaching-text">${escHtml(d.tipp)}</div>`;
    voigeTipp(card);added=true;
  }
  if(added){
    coachingScroll.scrollTop=coachingScroll.scrollHeight;
    updateKompaktCoaching(d);
  }
});

// ── Pause / Resume ────────────────────────────────────────────────────────────
async function togglePause(){
  try{
    const res=await fetch('/api/pause',{method:'POST'});
    const data=await res.json();
    paused=data.paused;
    // Pause/resume session timer alongside microphone state
    if(paused){
      if(sessionTimer){ clearInterval(sessionTimer); sessionTimer=null; }
    } else {
      startSessionTimer();
    }
    updatePauseUI();
  }catch(e){console.error('[PAUSE]',e);}
}
function updatePauseUI(){
  const btn=document.getElementById('pauseBtn');
  const dot=document.getElementById('dot');
  const ov=document.getElementById('pauseOverlay');
  const st=document.getElementById('st');
  const kpBtn=document.getElementById('kp-pauseBtn');
  const kpDot=document.getElementById('kp-dot');
  const kpSt=document.getElementById('kp-st');
  if(paused){
    btn.textContent='▶ Weiter';btn.classList.add('paused');
    dot.classList.add('paused');st.textContent='Pausiert';ov.classList.add('visible');
    if(kpBtn){kpBtn.textContent='▶ Weiter';kpBtn.classList.add('paused');}
    if(kpDot) kpDot.classList.add('paused');
    if(kpSt)  kpSt.textContent='Pausiert';
  }else{
    btn.textContent='⏸ Pause';btn.classList.remove('paused');
    dot.classList.remove('paused');st.textContent='Mikrofon aktiv';ov.classList.remove('visible');
    if(kpBtn){kpBtn.textContent='⏸ Pause';kpBtn.classList.remove('paused');}
    if(kpDot) kpDot.classList.remove('paused');
    if(kpSt)  kpSt.textContent='Mikrofon aktiv';
  }
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg){
  const t=document.getElementById('toast');
  t.textContent=msg;t.classList.add('visible');
  setTimeout(()=>t.classList.remove('visible'),3000);
}

// ── Escape HTML ───────────────────────────────────────────────────────────────
function escHtml(t){
  return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Gespräch beenden ──────────────────────────────────────────────────────────
async function beenden(){
  // Guard: no real conversation detected — show placeholder instead of fake postcall
  if(sessionSeconds < 10 || words < 20){
    const overlay=document.getElementById('postcall-overlay');
    if(overlay){
      overlay.style.display='flex';
      overlay.innerHTML=
        '<div class="n-glass" style="padding:32px;text-align:center;max-width:500px;margin:auto">' +
          '<h3 style="color:var(--page-text-color);margin-bottom:12px">Kein Gespräch erkannt</h3>' +
          '<p style="color:var(--page-text-secondary)">Es wurde kein ausreichendes Gespräch für eine Analyse erkannt.</p>' +
          '<a href="/dashboard" class="btn btn-primary" style="margin-top:16px">← Zurück zum Dashboard</a>' +
        '</div>';
    }
    return;
  }
  if(!confirm('Gespräch beenden?\nLog wird gespeichert und State zurückgesetzt.')) return;
  try{
    const res=await fetch('/api/beenden',{method:'POST'});
    const data=await res.json();
    if(!data.ok){alert('Fehler: '+(data.error||'?'));return;}
    stopSessionTimer();
    // UI leeren
    tr.innerHTML='<div class="msg final" style="border-color:#1a1a2e;color:#333350">Spreche ins Mikrofon …</div>';
    ai.innerHTML='<div class="msg final" style="border-color:#1a1a2e;color:#333350">Warte auf Gesprächsinhalt …</div>';
    coachingScroll.innerHTML='<div style="font-size:12px;color:#2a2500;padding:4px 0">Wartet auf Gesprächsinhalt …</div>';
    entferneSpinner();
    words=0;einwaende=0;analysen=0;letzteVersion=0;interim=null;tipCards.length=0;
    speech.beraterWords=0;speech.kundeWords=0;speech.beraterSegments=0;speech.startTime=null;
    document.getElementById('wc').textContent='0';
    document.getElementById('ec').textContent='0';
    document.getElementById('ac').textContent='0';
    updateSpeechCircles({redeanteil:0,tempo:0,monolog:0});
    // Kaufbereitschaft zurücksetzen
    updateKaufbereitschaft(30);
    // Kompakt-Panel zurücksetzen
    const kpE=document.getElementById('kp-einwand');if(kpE) kpE.textContent='Kein Einwand erkannt';
    const kpC=document.getElementById('kp-coaching');if(kpC) kpC.textContent='Wartet auf Gesprächsinhalt…';
    const kpP=document.getElementById('kp-painpointSec');if(kpP) kpP.style.display='none';
    updateKompaktMetrics(null,30);
    // Post-Call Modal zeigen (merge skript coverage from teleprompter)
    if(data.postcall){
      if(typeof getSkriptAbdeckung==='function'){
        const sk=getSkriptAbdeckung();
        if(sk) data.postcall.skript_abdeckung=sk;
      }
      zeigePostcall(data.postcall, data.filename||'');
    }
    showToast('✓ Gespräch gespeichert — '+(data.filename||''));
  }catch(e){console.error('[BEENDEN]',e);alert('Fehler: '+e.message);}
}

// ── Log Download ──────────────────────────────────────────────────────────────
async function downloadLog(){
  try{
    const res=await fetch('/api/log');const blob=await res.blob();
    const url=URL.createObjectURL(blob);const a=document.createElement('a');
    a.href=url;a.download='salesnerve_log_'+new Date().toISOString().slice(0,19).replace(/[:.]/g,'-')+'.txt';
    a.click();URL.revokeObjectURL(url);
  }catch(e){console.error('[LOG]',e);}
}

// ── Kaufbereitschaft UI ───────────────────────────────────────────────────────
function updateKaufbereitschaft(pct){
  const v=document.getElementById('kbValue');
  const b=document.getElementById('kbBar');
  if(!v||!b) return;
  v.textContent=pct+'%';
  b.style.width=pct+'%';
  let col,cls;
  if(pct<40){col='#e05c5c';cls='red';}
  else if(pct<70){col='#f0a500';cls='amber';}
  else{col='#E8B040';cls='green';}
  b.style.background=col;
  v.className='kb-value '+cls;
}

// ── Polling: Claude-Ergebnisse ────────────────────────────────────────────────
let letzteVersion=0;
let spinnerEl=null;
let _lastEinwandTyp = '';   // für Gegenargument-Tracking

function zeigeSpinner(){
  if(spinnerEl) return;
  spinnerEl=document.createElement('div');spinnerEl.className='spinner';
  spinnerEl.innerHTML='<div class="spin"></div>Claude analysiert…';
  ai.appendChild(spinnerEl);ai.scrollTop=ai.scrollHeight;
}
function entferneSpinner(){
  if(spinnerEl){spinnerEl.remove();spinnerEl=null;}
}

function zeigeKarte(d, lineId){
  entferneSpinner();analysen++;
  document.getElementById('ac').textContent=analysen;
  const card=document.createElement('div');
  if(lineId) card.dataset.lineId=lineId;
  const now=new Date().toLocaleTimeString('de-DE',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  if(!d.einwand){
    card.className='ai-card kein-einwand';
    card.innerHTML=`<div class="card-top"><span class="einwand-typ typ-kein">Kein Einwand</span><span class="card-time">${now}</span></div><div class="einwand-text">${escHtml(d.notiz||'Kein klarer Einwand erkennbar.')}</div>`;
  } else {
    einwaende++;document.getElementById('ec').textContent=einwaende;
    const isVersteckt = (d.typ||'').toLowerCase().includes('versteckt');
    const isVorwand   = d.ist_vorwand === true;
    const stufe  = isVersteckt ? 'versteckt' : (d.intensitaet==='hoch'?'einwand-hoch':'einwand');
    const typCls = isVersteckt ? 'typ-versteckt' : (isVorwand?'typ-vorwand':(d.intensitaet==='hoch'?'typ-hoch':'typ-mittel'));
    const intLabel= isVersteckt ? '🟠 Versteckt' : (d.intensitaet==='hoch'?'🔴 Hoch':'🟡 Mittel');
    const vorwandBadge = isVorwand
      ? `<span class="badge-vorwand">⚠ Vorwand</span>`
      : `<span class="badge-einwand">Einwand</span>`;
    const ga1 = d.gegenargument_1 || d.gegenargument || '';
    const ga2 = d.gegenargument_2 || '';
    _lastEinwandTyp = d.typ || '';
    const cardId = `card-${Date.now()}`;
    card.id = cardId;
    card.className=`ai-card ${stufe}`;
    card.innerHTML=`
      <div class="card-top">
        ${vorwandBadge}
        <span class="einwand-typ ${typCls}">${escHtml(d.typ)}</span>
        <span class="intensitaet">${intLabel}</span>
        <span class="card-time">${now}</span>
      </div>
      <div><div class="card-label">Erkannter Einwand</div><div class="einwand-text">"${escHtml(d.einwand_zitat)}"</div></div>
      <div style="display:flex;align-items:flex-start;gap:8px">
        <div style="flex:1"><div class="card-label">Option 1</div><div class="argument-text">${escHtml(ga1)}</div></div>
        <button class="ga-nutzen-btn" id="${cardId}-opt1" onclick="logGenutzt('${cardId}',1,'${escHtml(d.typ).replace(/'/g,"\\'")}')">✓ Genutzt</button>
      </div>
      ${ga2?`<div style="display:flex;align-items:flex-start;gap:8px">
        <div style="flex:1"><div class="card-label">Option 2</div><div class="argument-text argument-text-alt">${escHtml(ga2)}</div></div>
        <button class="ga-nutzen-btn" id="${cardId}-opt2" onclick="logGenutzt('${cardId}',2,'${escHtml(d.typ).replace(/'/g,"\\'")}')">✓ Genutzt</button>
      </div>`:''}`;
  }
  ai.appendChild(card);ai.scrollTop=ai.scrollHeight;
  updateKompaktEinwand(d);
}

setInterval(async()=>{
  try{
    const res=await fetch('/api/ergebnis');const data=await res.json();
    if(data.aktiv&&!paused) zeigeSpinner();
    if(data.version>letzteVersion&&data.ergebnis!==null){
      letzteVersion=data.version;
      zeigeKarte(data.ergebnis,data.line_id||null);
    }
    if(typeof data.kaufbereitschaft==='number'){
      updateKaufbereitschaft(data.kaufbereitschaft);
    }
    if(data.speech_stats) updateSpeechCircles(data.speech_stats);
    updateKompaktMetrics(data.speech_stats||null, data.kaufbereitschaft||null);
  }catch(e){console.error('[POLL] Fehler:',e);}
},500);

// ── Gegenargument "Genutzt" Tracking ─────────────────────────────────────────
function logGenutzt(cardId, option, einwandTyp){
  // Beide Buttons dieser Karte deaktivieren
  [1,2].forEach(opt => {
    const btn = document.getElementById(`${cardId}-opt${opt}`);
    if(!btn) return;
    btn.disabled = true;
    if(opt === option){
      btn.textContent = '✓';
      btn.style.background = '#0d2a1e';
      btn.style.borderColor = '#E8B040';
      btn.style.color = '#E8B040';
    } else {
      btn.style.opacity = '0.3';
    }
  });
  const kb = parseInt(document.getElementById('kbValue')?.textContent) || 30;
  fetch('/api/log_gegenargument_wahl', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({gewaehlte_option: option, kb_aktuell: kb, einwand_typ: einwandTyp})
  }).catch(()=>{});
}

// ── Quick Actions ─────────────────────────────────────────────────────────────
function quickAction(typ){
  const prompts = {
    frage:     'Welche offene Frage sollte ich dem Kunden jetzt stellen basierend auf dem bisherigen Gespräch?',
    einwand:   'Der Kunde hat gerade einen Einwand gebracht. Wie kann ich ihn entkräften?',
    uebergang: 'Wie kann ich jetzt natürlich zum nächsten Gesprächsthema überleiten?',
    abschluss: 'Wie kann ich das Gespräch jetzt in Richtung Abschluss lenken?',
  };
  const inp = document.getElementById('frageInput');
  if (inp) { inp.value = prompts[typ] || ''; inp.focus(); }
}

// ── Frage stellen ─────────────────────────────────────────────────────────────
function openFrageModal(){
  document.getElementById('frageOverlay').classList.add('open');
  document.getElementById('frageInput').focus();
  document.getElementById('frageAntwort').innerHTML='';
}
function closeFrageModal(){
  document.getElementById('frageOverlay').classList.remove('open');
}
function closeFrageOnOverlay(e){
  if(e.target===document.getElementById('frageOverlay')) closeFrageModal();
}
// Keyboard shortcut: Escape
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){closeFrageModal();}
});

async function sendeFrageAnKI(){
  const frage=document.getElementById('frageInput').value.trim();
  if(!frage) return;
  const antwortDiv=document.getElementById('frageAntwort');
  antwortDiv.innerHTML='<div style="color:#8866cc;font-size:13px;font-style:italic;padding:8px 0">Claude denkt…</div>';
  try{
    // Detect typ from quick-action prompts
    const _qa_typ = ['frage','einwand','uebergang','abschluss'].find(t =>
      frage.toLowerCase().includes(t)) || 'frage';
    const res=await fetch('/api/frage',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({frage, context: recentSegments.slice(-3), typ: _qa_typ})
    });
    const data=await res.json();
    if(data.ok){
      const card=document.createElement('div');card.className='frage-antwort-card';
      let secs=60;
      card.innerHTML=`<div class="frage-antwort-timer" id="faTimer">${secs}s</div><div>${escHtml(data.antwort)}</div>`;
      antwortDiv.innerHTML='';antwortDiv.appendChild(card);
      // Auto-Countdown
      const ti=setInterval(()=>{
        secs--;const el=card.querySelector('#faTimer');
        if(el) el.textContent=secs+'s';
        if(secs<=0){clearInterval(ti);card.style.opacity='0';setTimeout(()=>card.remove(),600);}
      },1000);
    } else {
      antwortDiv.innerHTML='<div style="color:#e05c5c;font-size:13px;padding:4px 0">Fehler: '+escHtml(data.error||'?')+'</div>';
    }
  }catch(e){
    antwortDiv.innerHTML='<div style="color:#e05c5c;font-size:13px;padding:4px 0">Verbindungsfehler</div>';
  }
}

// ── Post-Call Modal ───────────────────────────────────────────────────────────
let pcFilename='';
let pcData=null;
let selectedStern=0;

function zeigePostcall(d, filename){
  pcData=d; pcFilename=filename; selectedStern=0;
  document.getElementById('postcallOverlay').classList.add('open');

  // Redeanteil
  const total=(d.berater_words||0)+(d.kunde_words||0);
  const bPct=total?Math.round(d.berater_words/total*100):50;
  const kPct=100-bPct;
  document.getElementById('pc-rBerater').style.width=bPct+'%';
  document.getElementById('pc-rKunde').style.width=kPct+'%';
  document.getElementById('pc-rBerater').textContent='B '+bPct+'%';
  document.getElementById('pc-rKunde').textContent='K '+kPct+'%';
  document.getElementById('pc-rText').textContent=`Berater: ${bPct}% / Kunde: ${kPct}%`;

  // Kaufbereitschaft
  document.getElementById('pc-kbStart').textContent=(d.kb_start||30)+'%';
  document.getElementById('pc-kbEnd').textContent=(d.kb_end||30)+'%';
  // Verlauf-Chart
  const vDiv=document.getElementById('pc-kbVerlauf');vDiv.innerHTML='';
  if(d.kb_verlauf&&d.kb_verlauf.length){
    d.kb_verlauf.forEach(v=>{
      const bar=document.createElement('div');bar.className='kb-bar-item';
      const h=Math.round(v.wert/2);// max 50px
      bar.style.height=h+'px';
      bar.style.background=v.wert<40?'#e05c5c':(v.wert<70?'#f0a500':'#E8B040');
      bar.title=v.ts+': '+v.wert+'%';vDiv.appendChild(bar);
    });
  }

  // Einwände
  const einList=document.getElementById('pc-einList');einList.innerHTML='';
  document.getElementById('pc-einCount').textContent=(d.einwaende||[]).length;
  (d.einwaende||[]).forEach(e=>{
    const row=document.createElement('div');row.className='einwand-row';
    const col=e.intensitaet==='hoch'?'#e05c5c':'#f0a05a';
    row.innerHTML=`<span class="einwand-badge-small" style="background:${col}20;color:${col}">${escHtml(e.typ)}</span><span style="font-size:12px;color:#8888aa">${escHtml(e.zitat||'').slice(0,50)}</span>`;
    einList.appendChild(row);
  });

  // Kaufsignale
  const sigList=document.getElementById('pc-sigList');sigList.innerHTML='';
  document.getElementById('pc-sigCount').textContent=(d.kaufsignale||[]).length;
  (d.kaufsignale||[]).forEach(s=>{
    const div=document.createElement('div');
    div.style.cssText='font-size:12px;color:#E8B040;display:flex;gap:6px;align-items:flex-start';
    div.innerHTML=`<span>✓</span><span>${escHtml(s.text)}</span>`;sigList.appendChild(div);
  });

  // Painpoints
  const ppList=document.getElementById('pc-ppList');ppList.innerHTML='';
  document.getElementById('pc-ppCount').textContent=(d.painpoints||[]).length;
  (d.painpoints||[]).forEach(p=>{
    const div=document.createElement('div');
    div.style.cssText='font-size:12px;color:#e07030;display:flex;gap:6px;align-items:flex-start';
    div.innerHTML=`<span>📍</span><span>${escHtml(p.text)}</span>`;ppList.appendChild(div);
  });

  // Skript-Abdeckung
  const sa = d.skript_abdeckung;
  const scriptSection = document.getElementById('pc-scriptSection');
  if (sa && sa.phasen && sa.phasen.length) {
    scriptSection.style.display = '';
    document.getElementById('pc-scriptPct').textContent = sa.gesamt_prozent || 0;
    const phList = document.getElementById('pc-scriptPhasen');
    phList.innerHTML = '';
    sa.phasen.forEach(p => {
      // Teleprompter format: {phase, items, done, total, pct}
      // Server format: {name, abgedeckt}
      const name     = p.phase || p.name || '';
      const abgedeckt = p.items ? (p.done > 0) : p.abgedeckt;
      const pct      = p.pct != null ? p.pct : (p.abgedeckt ? 100 : 0);
      const col = abgedeckt ? '#E8B040' : '#333350';
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'margin-bottom:6px';
      let inner = `<div style="display:flex;align-items:center;gap:5px;font-size:12px;background:#0c0c18;border:1px solid ${abgedeckt?'#1e2e28':'#1a1a28'};border-radius:6px;padding:4px 9px">
        <span style="color:${col};font-size:13px">${abgedeckt?'✓':'○'}</span>
        <span style="color:${abgedeckt?'#c0c0d5':'#444466'}">${escHtml(name)}</span>
        ${p.total ? `<span style="margin-left:auto;font-size:10px;color:#6b6b80">${p.done||0}/${p.total} (${pct}%)</span>` : ''}
      </div>`;
      if(p.items && p.items.length){
        inner += `<div style="padding:3px 0 0 18px;display:flex;flex-direction:column;gap:2px">`;
        p.items.forEach(it=>{
          inner += `<div style="font-size:11px;display:flex;gap:5px;color:${it.checked?'#444466':'#888899'}">
            <span style="color:${it.checked?'#E8B040':'#333350'}">${it.checked?'✓':'○'}</span>
            <span style="${it.checked?'text-decoration:line-through':''}">${escHtml(it.text)}</span>
          </div>`;
        });
        inner += `</div>`;
      }
      wrapper.innerHTML = inner;
      phList.appendChild(wrapper);
    });
  } else if (scriptSection) {
    scriptSection.style.display = 'none';
  }

  // CRM-Notiz
  const crmSection = document.getElementById('pc-crmSection');
  const crmNotizEl = document.getElementById('pc-crmNotiz');
  if (d.crm_notiz && crmSection) {
    crmSection.style.display = '';
    crmNotizEl.textContent = d.crm_notiz;
  } else if (crmSection) {
    crmSection.style.display = 'none';
  }

  // Follow-up Email
  const emailSection = document.getElementById('pc-emailSection');
  const emailEl = document.getElementById('pc-followupEmail');
  if (d.followup_email && emailSection) {
    emailSection.style.display = '';
    // Split Betreff from body
    const lines = d.followup_email.split('\n');
    const subjectLine = lines[0] || '';
    const body = lines.slice(1).join('\n').trim();
    emailEl.textContent = d.followup_email;
    const subject = subjectLine.replace(/^Betreff:\s*/i, '');
    const mailtoEl = document.getElementById('pc-mailtoBtn');
    if (mailtoEl) {
      mailtoEl.href = 'mailto:?subject=' + encodeURIComponent(subject) + '&body=' + encodeURIComponent(body);
    }
  } else if (emailSection) {
    emailSection.style.display = 'none';
  }

  // Nächste Schritte
  const stepsSection = document.getElementById('pc-stepsSection');
  const stepsList = document.getElementById('pc-stepsList');
  if (d.naechste_schritte && d.naechste_schritte.length && stepsSection) {
    stepsSection.style.display = '';
    stepsList.innerHTML = '';
    d.naechste_schritte.forEach(s => {
      const div = document.createElement('div');
      div.className = 'ns-item';
      div.innerHTML = `<div class="ns-check" onclick="toggleNsCheck(this)"></div><span class="ns-text">${escHtml(s)}</span>`;
      stepsList.appendChild(div);
    });
  } else if (stepsSection) {
    stepsSection.style.display = 'none';
  }

  // Sterne zurücksetzen
  document.querySelectorAll('.stern').forEach(s=>s.classList.remove('active'));
  document.getElementById('sterneHint').textContent='Klicke zum Bewerten';
  document.getElementById('sterneKommentar').value='';

  // Claude Insights laden
  loadPostcallInsights(d);
}

async function loadPostcallInsights(d){
  try{
    const res=await fetch('/api/postcall_insights',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        einwaende:d.einwaende||[],painpoints:d.painpoints||[],
        kb_start:d.kb_start||30,kb_end:d.kb_end||30
      })
    });
    const result=await res.json();
    const ul=document.getElementById('pc-bullets');ul.innerHTML='';
    (result.bullets||[]).forEach(b=>{
      if(!b) return;
      const li=document.createElement('li');li.className='bullet-item';
      li.innerHTML=`<span class="bullet-dot">·</span><span>${escHtml(b)}</span>`;
      ul.appendChild(li);
    });
  }catch(e){console.error('[INSIGHTS]',e);}
}

function closePostcall(){
  document.getElementById('postcallOverlay').classList.remove('open');
}

// ── Stern-Bewertung ───────────────────────────────────────────────────────────
function setStern(n){
  selectedStern=n;
  document.querySelectorAll('.stern').forEach(s=>{
    const sv=parseInt(s.dataset.s);
    s.classList.toggle('active',sv<=n);
  });
  document.getElementById('sterneHint').textContent=['','Schlecht','Ausbaufähig','Ok','Gut','Sehr gut'][n]||'';
}
// Hover-Effekt
document.querySelectorAll('.stern').forEach(s=>{
  s.addEventListener('mouseenter',()=>{
    const n=parseInt(s.dataset.s);
    document.querySelectorAll('.stern').forEach(ss=>ss.classList.toggle('hover',parseInt(ss.dataset.s)<=n));
  });
  s.addEventListener('mouseleave',()=>{
    document.querySelectorAll('.stern').forEach(ss=>ss.classList.remove('hover'));
  });
});

async function saveFeedback(){
  if(!selectedStern){showToast('Bitte zuerst Sterne vergeben.');return;}
  const btn=document.getElementById('pc-saveBtn');
  btn.textContent='Speichert…';btn.disabled=true;
  try{
    const res=await fetch('/api/feedback',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        stars:selectedStern,
        comment:document.getElementById('sterneKommentar').value,
        session_log_id:pcFilename
      })
    });
    const data=await res.json();
    if(data.ok){btn.textContent='✓ Gespeichert';showToast('Bewertung gespeichert. Danke!');}
    else{btn.textContent='Fehler';btn.disabled=false;}
  }catch(e){btn.textContent='Fehler';btn.disabled=false;}
}

// ── CRM Export Helpers ────────────────────────────────────────────────────────
async function copyCrm(elId, btn){
  const text = document.getElementById(elId)?.textContent || '';
  try {
    await navigator.clipboard.writeText(text);
    const orig = btn.textContent;
    btn.textContent = '✓ Kopiert!';
    btn.classList.add('copied');
    setTimeout(()=>{ btn.textContent=orig; btn.classList.remove('copied'); }, 2000);
  } catch(e) {
    showToast('Kopieren nicht möglich');
  }
}

function toggleNsCheck(el){
  el.classList.toggle('checked');
  if (el.classList.contains('checked')) el.textContent = '✓';
  else el.textContent = '';
  const textEl = el.nextElementSibling;
  if (textEl) textEl.style.textDecoration = el.classList.contains('checked') ? 'line-through' : '';
}

// ── Kompakt-Panel Update Helpers ──────────────────────────────────────────────
function updateKompaktEinwand(d){
  const el=document.getElementById('kp-einwand');
  if(!el) return;
  if(!d||!d.einwand){
    el.style.color='#444466';
    el.textContent=d&&d.notiz?d.notiz:'Kein Einwand erkannt';
  }else{
    const isVorwand=d.ist_vorwand===true;
    const label=isVorwand?'⚠ Vorwand':'⚡ Einwand';
    const col=d.intensitaet==='hoch'?'#e05c5c':'#f0a05a';
    el.style.color=col;
    const ga1=d.gegenargument_1||d.gegenargument||'';
    el.textContent=`${label} · ${d.typ||'?'} — ${d.einwand_zitat||''}\n${ga1}`;
  }
}
function updateKompaktCoaching(d){
  if(d.painpoint){
    const sec=document.getElementById('kp-painpointSec');
    const el=document.getElementById('kp-painpoint');
    if(sec) sec.style.display='';
    if(el)  el.textContent=d.painpoint;
  }
  if(d.tipp){
    const el=document.getElementById('kp-coaching');
    if(el){el.style.color='#c8922a';el.textContent=d.tipp;}
  }
}
function updateKompaktMetrics(stats, kb){
  if(stats){
    [['redeanteil','%','ra'],['tempo','','wpm'],['monolog','s','mono']].forEach(([key,unit,id])=>{
      const val    = stats[key];
      const span   = document.getElementById('kp-m-'+id);
      const circle = document.getElementById('kp-mc-'+id);
      if(span)   span.textContent = val!==undefined ? val+unit : '–';
      if(circle && val!==undefined){
        const col = mcColor(key, val);
        circle.style.borderColor = col;
        circle.style.color       = col;
      }
    });
  }
  if(kb!==null&&kb!==undefined){
    const el  = document.getElementById('kp-m-kb');
    const bar = document.getElementById('kp-kb-bar2');
    const col = kb>=60 ? '#E8B040' : (kb>=30 ? '#f0a500' : '#e05c5c');
    if(el){ el.textContent=kb+'%'; el.style.color=col; }
    if(bar){ bar.style.width=Math.min(kb,100)+'%'; bar.style.background=col; }
  }
}
