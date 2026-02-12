function qs(sel){ return document.querySelector(sel); }
function qsa(sel){ return Array.from(document.querySelectorAll(sel)); }

function setStrength(pw){
  const bar = qs("#pwBar");
  const text = qs("#pwText");
  if(!bar || !text) return;

  let score = 0;
  if(pw.length >= 8) score++;
  if(/[A-Z]/.test(pw)) score++;
  if(/[a-z]/.test(pw)) score++;
  if(/\d/.test(pw)) score++;
  if(/[^\w\s]/.test(pw)) score++;

  const pct = Math.min(100, Math.round((score/5)*100));
  bar.style.width = pct + "%";

  const labels = ["Very weak", "Weak", "Okay", "Strong", "Very strong"];
  const label = pw ? labels[Math.max(0, score-1)] : "Type password";
  text.textContent = label;
}

function togglePassword(btnId, inputId){
  const btn = qs(btnId);
  const inp = qs(inputId);
  if(!btn || !inp) return;
  btn.addEventListener("click", ()=>{
    inp.type = inp.type === "password" ? "text" : "password";
    btn.textContent = inp.type === "password" ? "Show" : "Hide";
  });
}

function formatCardInput(){
  const inp = qs("#card_number");
  if(!inp) return;
  inp.addEventListener("input", ()=>{
    let v = inp.value.replace(/\D/g, "").slice(0, 16);
    inp.value = v.replace(/(.{4})/g, "$1 ").trim();
  });
}

function tiltCards(){
  const cards = qsa(".tilt");
  if(!cards.length) return;

  cards.forEach(card=>{
    card.addEventListener("mousemove", (e)=>{
      const r = card.getBoundingClientRect();
      const x = e.clientX - r.left;
      const y = e.clientY - r.top;
      const rx = ((y / r.height) - 0.5) * -6;
      const ry = ((x / r.width) - 0.5) *  8;
      card.style.transform = `perspective(900px) rotateX(${rx}deg) rotateY(${ry}deg) translateY(-2px)`;
    });
    card.addEventListener("mouseleave", ()=>{
      card.style.transform = "";
    });
  });
}

function startClock(){
  const el = qs("#liveClock");
  if(!el) return;
  const tick = ()=>{
    const d = new Date();
    el.textContent = d.toLocaleString(undefined, {weekday:"short", day:"2-digit", month:"short", hour:"2-digit", minute:"2-digit"});
  };
  tick();
  setInterval(tick, 1000 * 20);
}

function drawSparkline(values){
  const canvas = qs("#spark");
  if(!canvas) return;

  const ctx = canvas.getContext("2d");
  const w = canvas.width = canvas.clientWidth * devicePixelRatio;
  const h = canvas.height = canvas.clientHeight * devicePixelRatio;
  ctx.clearRect(0,0,w,h);

  const pad = 10 * devicePixelRatio;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);

  const xStep = (w - pad*2) / Math.max(1, values.length - 1);

  const y = (v)=> {
    const t = (v - min) / (max - min || 1);
    return (h - pad) - t * (h - pad*2);
  };

  ctx.lineWidth = 2.2 * devicePixelRatio;
  ctx.beginPath();
  values.forEach((v,i)=>{
    const px = pad + xStep*i;
    const py = y(v);
    if(i === 0) ctx.moveTo(px, py);
    else ctx.lineTo(px, py);
  });
  ctx.strokeStyle = "rgba(255,255,255,0.70)";
  ctx.stroke();

  // glow
  ctx.shadowColor = "rgba(34,211,238,0.35)";
  ctx.shadowBlur = 12 * devicePixelRatio;
  ctx.strokeStyle = "rgba(34,211,238,0.35)";
  ctx.stroke();
  ctx.shadowBlur = 0;
}

async function loadTransactions(){
  const body = qs("#txBody");
  const hint = qs("#txHint");
  if(!body) return;

  // skeleton rows
  body.innerHTML = `
    <tr><td colspan="5"><div class="skeleton" style="height:44px;"></div></td></tr>
    <tr><td colspan="5"><div class="skeleton" style="height:44px;"></div></td></tr>
    <tr><td colspan="5"><div class="skeleton" style="height:44px;"></div></td></tr>
  `;

  try{
    const res = await fetch("/api/transactions");
    const data = await res.json();
    const items = data.items || [];

    if(hint) hint.textContent = `Last sync: ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"})}`;

    // sparkline from amounts
    const values = items.slice(0, 10).map(x=>x.amount).reverse();
    if(values.length) drawSparkline(values);

    body.innerHTML = items.map(t=>{
      const statusClass = t.status === "Success" ? "pillTag good" : "pillTag warn";
      const statusDot = t.status === "Success"
        ? `<span style="width:7px;height:7px;border-radius:999px;background:rgba(52,211,153,.95);box-shadow:0 0 0 3px rgba(52,211,153,.10)"></span>`
        : `<span style="width:7px;height:7px;border-radius:999px;background:rgba(251,191,36,.95);box-shadow:0 0 0 3px rgba(251,191,36,.10)"></span>`;

      return `
        <tr>
          <td>${t.tx_type}</td>
          <td>${t.merchant}</td>
          <td><b>₹ ${t.amount}</b></td>
          <td><span class="${statusClass}">${statusDot}${t.status}</span></td>
          <td>${t.time}</td>
        </tr>
      `;
    }).join("");

  }catch(e){
    body.innerHTML = `<tr><td colspan="5">Unable to load transactions.</td></tr>`;
  }
}

document.addEventListener("DOMContentLoaded", ()=>{
  // strength meter
  const pw = qs("#password");
  if(pw){
    pw.addEventListener("input", ()=>setStrength(pw.value));
    setStrength(pw.value || "");
  }

  // show/hide password
  togglePassword("#pwToggle", "#password");
  togglePassword("#pwToggle2", "#password2");

  // card formatting
  formatCardInput();

  // premium interactions
  tiltCards();
  startClock();

  // dashboard
  loadTransactions();
});
