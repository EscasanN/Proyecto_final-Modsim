"use strict";
const $ = id => document.getElementById(id);
let payload = null, panelState = null, token = "", playing = false, position = 0;
let previousFrame = 0, renderedIndex = -1, lastJobKey = "", busy = false, rainTimer, trajectoryRequest = 0;
const number = (value, digits = 1) => Number(value).toLocaleString("es-GT", {minimumFractionDigits: digits, maximumFractionDigits: digits});
const isTrue = value => value === true || value === "True" || value === "true";
const originLabel = origin => ({synthetic: "Ejemplo sintético", public: "Datos reales públicos · Chase (2026)", observed: "Mediciones propias"})[origin] || origin;
const dateLabel = value => new Intl.DateTimeFormat("es-GT", {timeZone: "America/Guatemala", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false}).format(new Date(value));

function toast(message) {
  $("toast").textContent = message; $("toast").hidden = false;
  clearTimeout(toast.timeout); toast.timeout = setTimeout(() => $("toast").hidden = true, 6000);
}
async function api(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Error ${response.status}`);
  return body;
}
function pause() {
  playing = false; $("play").textContent = "▶"; $("play").setAttribute("aria-label", "Reproducir trayectoria");
}
async function loadTrajectory() {
  const request = ++trajectoryRequest;
  pause();
  const source = $("source").value;
  $("condition").disabled = source === "simulation";
  $("seed").disabled = source === "simulation";
  const params = new URLSearchParams({source, condition: $("condition").value});
  if (source === "experiments" && $("seed").value) params.set("seed", $("seed").value);
  try {
    const data = await api(`/api/trajectory?${params}`);
    if (request !== trajectoryRequest) return;
    payload = data;
    if (data.seeds.length) {
      $("seed").replaceChildren(...data.seeds.map(seed => new Option(String(seed), String(seed), false, seed === data.seed)));
    }
    payload.start = Date.parse(data.trajectory[0].timestamp);
    payload.end = Date.parse(data.trajectory.at(-1).timestamp);
    payload.times = data.trajectory.map(row => Date.parse(row.timestamp));
    position = 0; renderedIndex = -1;
    $("origin").textContent = originLabel(data.data_origin);
    $("limit").textContent = number(data.safe_deficit_ml, 0);
    const feasible = isTrue(data.metrics.feasible);
    $("feasibility").textContent = feasible ? "✓ Ejecución completa factible" : "! Ejecución completa no factible";
    $("feasibility").classList.toggle("unsafe", !feasible);
    $("trajectory-note").textContent = source === "experiments" ? `${data.condition} · semilla ${data.seed} · auditor de C` : `${data.metrics.method.toUpperCase()} · paso ${data.metrics.step_h} h · política fija`;
    drawChart(); renderPosition();
  } catch (error) {
    if (request !== trajectoryRequest) return;
    toast(error.message);
    // Se conserva una trayectoria anterior solo con sus controles originales.
    if (payload) {
      $("source").value = payload.source; $("condition").value = payload.condition;
      $("condition").disabled = payload.source === "simulation"; $("seed").disabled = payload.source === "simulation";
    }
  }
}
function drawChart() {
  if (!payload) return;
  const width = 900, height = 165, left = 33, right = 12, top = 13, bottom = 27;
  const maxD = Math.max(payload.safe_deficit_ml * 1.15, ...payload.trajectory.map(r => r.deficit_ml)) || 1;
  const duration = payload.end - payload.start || 1;
  const x = time => left + (time - payload.start) / duration * (width-left-right);
  const y = d => height-bottom - d/maxD * (height-top-bottom);
  const path = payload.trajectory.map((r, i) => `${i ? "L" : "M"}${x(payload.times[i]).toFixed(2)},${y(r.deficit_ml).toFixed(2)}`).join(" ");
  let grid = "";
  for (let i=0;i<4;i++) {
    const d = i*maxD/3, py = y(d);
    grid += `<line x1="${left}" y1="${py}" x2="${width-right}" y2="${py}" stroke="#e1e3d9"/><text x="${left-7}" y="${py+3}" text-anchor="end">${Math.round(d)}</text>`;
  }
  for (let i=0;i<5;i++) {
    const time = payload.start + duration*i/4;
    grid += `<text x="${x(time)}" y="${height-6}" text-anchor="middle">${Math.round(duration*i/4/3600000)} h</text>`;
  }
  // Solo se interpolan coordenadas numéricas; nunca HTML procedente de archivos.
  $("chart").innerHTML = `${grid}<line x1="${left}" y1="${y(payload.safe_deficit_ml)}" x2="${width-right}" y2="${y(payload.safe_deficit_ml)}" stroke="#ae684d" stroke-dasharray="5 5"/><path d="${path}" fill="none" stroke="#49664b" stroke-width="2"/><line id="chart-cursor" x1="${left}" x2="${left}" y1="${top}" y2="${height-bottom}" stroke="#9aab8b" stroke-width="1"/><circle id="chart-point" cx="${left}" cy="${y(0)}" r="4" fill="#49664b" stroke="#f7f6f0" stroke-width="2"/>`;
  payload.chart = {x, y};
}
function renderPosition() {
  if (!payload) return;
  const time = payload.start + position*(payload.end-payload.start);
  let lo=0, hi=payload.times.length-1;
  while (lo < hi) {const mid=Math.ceil((lo+hi)/2); if (payload.times[mid]<=time) lo=mid; else hi=mid-1;}
  const i=lo, row=payload.trajectory[i];
  const ratio = Math.max(0, Math.min(1, row.deficit_ml / payload.safe_deficit_ml));
  $("deficit").textContent = number(row.deficit_ml);
  $("water").textContent = number(row.irrigation_ml);
  $("drainage").textContent = number(row.drainage_ml);
  $("deficit-bar").style.width = `${ratio*100}%`;
  $("deficit-bar").style.background = row.deficit_ml > payload.safe_deficit_ml ? "#ae684d" : "#49664b";
  $("scene-date").textContent = dateLabel(row.timestamp);
  $("plant-state").textContent = row.deficit_ml > payload.safe_deficit_ml ? "Sobre el límite" : "Dentro del límite";
  const y = 278 + ratio*109;
  $("water-level").setAttribute("y", String(y));
  $("water-line").setAttribute("transform", `translate(0 ${y-310})`);
  $("timeline").value = String(Math.round(position*1000));
  $("progress-label").textContent = `${Math.round(position*100)} %`;
  const x=payload.chart.x(payload.times[i]);
  $("chart-cursor").setAttribute("x1",String(x)); $("chart-cursor").setAttribute("x2",String(x));
  $("chart-point").setAttribute("cx",String(x)); $("chart-point").setAttribute("cy",String(payload.chart.y(row.deficit_ml)));
  const events = payload.events.filter(e => Date.parse(e.timestamp) <= payload.times[i]);
  const event=events.at(-1);
  $("event-label").textContent = event ? `${event.kind === "final_refill" ? "Reposición final" : "Último riego"}: ${number(event.irrigation_ml)} mL` : "Antes del primer riego";
  if (renderedIndex>=0 && i>renderedIndex && payload.trajectory.slice(renderedIndex+1,i+1).some(r => ["irrigation","final_refill"].includes(r.stage))) {
    $("scene").classList.add("watering"); clearTimeout(rainTimer);
    rainTimer=setTimeout(() => $("scene").classList.remove("watering"), 1100);
  }
  renderedIndex=i;
}
function animate(now) {
  if (playing && payload) {
    position=Math.min(1, position + Math.min(now-previousFrame,150)/1000/Number($("speed").value));
    renderPosition(); if (position>=1) pause();
  }
  previousFrame=now; requestAnimationFrame(animate);
}
function taskButton(task,index) {
  const button=document.createElement("button"); button.className="task"; button.dataset.task=task.id;
  const ordinal=document.createElement("span"); ordinal.className="task-index"; ordinal.textContent=String(index+1).padStart(2,"0");
  const text=document.createElement("span"); text.className="task-text";
  const title=document.createElement("strong"); title.textContent=task.title;
  const detail=document.createElement("small"); detail.textContent=task.detail;
  const arrow=document.createElement("span"); arrow.className="task-arrow"; arrow.textContent="↗";
  text.append(title,detail); button.append(ordinal,text,arrow);
  button.addEventListener("click",()=>runTask(task)); return button;
}
async function runTask(task) {
  if (busy) return;
  if (task.id === "optimize" && !window.confirm("Ejecutar 30 búsquedas por variante puede tardar varios minutos. Se guardarán en results/presentation/optimization, sin modificar la política de evaluación. ¿Iniciar?")) return;
  busy=true; updateButtons();
  try {
    await api("/api/run", {method:"POST",headers:{"Content-Type":"application/json","X-Panel-Token":token},
      body:JSON.stringify({task:task.id,options:{method:$("method").value,step_h:$("step").value}})});
    pause(); await refreshState();
  } catch(error) {toast(error.message);busy=false;updateButtons();}
}
function updateButtons() {document.querySelectorAll("button.task").forEach(b=>b.disabled=busy); $("runner-light").classList.toggle("busy",busy);}
function updateSummary(state) {
  const body=$("summary-body"); body.replaceChildren();
  for (const name of ["B0","O0","B1","O1"]) {
    const r=state.summary.find(r=>r.condition===name); if (!r) continue;
    const tr=document.createElement("tr");
    const values=[name,`${number(r.total_irrigation_ml_mean)} ± ${r.total_irrigation_ml_sd ? number(r.total_irrigation_ml_sd) : "—"}`,`${Math.round(Number(r.feasible_fraction)*Number(r.n_runs))} / ${r.n_runs}`,number(r.final_refill_ml_mean)];
    values.forEach((v,i)=>{const td=document.createElement("td");td.textContent=v;if(i===2){td.className="table-status"+(Number(r.feasible_fraction)<1?" warn":"");}tr.append(td);}); body.append(tr);
  }
  $("interpretation").textContent=state.summary.length ? "Un menor consumo no basta: una política debe cumplir las restricciones. El agua total incluye la reposición final. B: base; O: optimizada; 0: normal; 1: pérdidas +20 %." : "Ejecuta la comparación para generar resultados. No hay resultados disponibles todavía.";
  const v=state.validation.find(r=>r.pot_id==="ALL");
  const vNote={public:"Validación con datos reales públicos (enset, segunda semana sin recalibrar)",synthetic:"Validación sintética · no constituye validación real",observed:"Validación con mediciones propias"}[state.validation_origin]||"Validación";
  $("validation-result").textContent=v?`${vNote} · ${v.n_observations} observaciones reservadas · MAE ${number(v.mae_ml,1)} mL · RMSE ${number(v.rmse_ml,1)} mL · sesgo ${number(v.bias_ml,1)} mL.`:"Validación: ejecuta «Validar predicciones» para calcular errores reservados.";
  $("real-pending").textContent=state.real_status;
  $("artifacts").replaceChildren(...(state.artifacts||[]).map(item=>{
    const link=document.createElement("a");link.href=item.url;link.textContent=item.label+" ↓";
    link.setAttribute("download","");return link;
  }));
  const figures=$("figures");
  if (JSON.stringify(state.figures)!==figures.dataset.paths) {
    figures.dataset.paths=JSON.stringify(state.figures); figures.replaceChildren();
    state.figures.forEach((path,i)=>{const a=document.createElement("a");a.href=path;a.target="_blank";a.rel="noopener";
      const img=document.createElement("img");img.src=path;const names={"01_system":"Dinámica del sistema","02_policies":"Comparación de políticas","03_sensitivity":"Sensibilidad y factibilidad","04_validation_all":"Validación en las 21 macetas"};img.alt=names[path.split("/").pop().replace(".png","")]||"Figura";
      a.append(img,document.createTextNode(`${String(i+1).padStart(2,"0")} / ${img.alt} ↗`));figures.append(a);});
  }
}
async function refreshState() {
  try {
    const state=await api("/api/state"); panelState=state;token=state.token;
    if (!$("tasks").children.length) state.tasks.forEach((t,i)=>$(t.group==="advanced"?"advanced-task":"tasks").append(taskButton(t,i)));
    const job=state.job;busy=job?.status==="running";updateButtons();
    if (job) {
      const title=state.tasks.find(t=>t.id===job.task)?.title||job.task;
      $("console-title").textContent=title;
      const log=$("console"); const atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<40;
      if(log.textContent!==job.log){log.textContent=job.log||"Iniciando…";if(atBottom)log.scrollTop=log.scrollHeight;}
      $("job-status").textContent=busy?"En ejecución · puedes seguir explorando la maceta":job.status==="success"?"✓ Completado · código de salida 0":`! La tarea terminó con código ${job.exit_code} · revisa la salida`;
      $("job-duration").textContent=`${Math.round((Date.parse(job.finished_at||new Date().toISOString())-Date.parse(job.started_at))/1000)} s`;
      document.querySelectorAll("button.task").forEach(b=>{
        const latest=state.history.filter(h=>h.task===b.dataset.task).at(-1);
        const active=job.task===b.dataset.task&&busy;
        b.classList.toggle("running",active);b.classList.toggle("done",!active&&latest?.status==="success");b.classList.toggle("failed",!active&&latest?.status==="error");
        b.querySelector(".task-arrow").textContent=active?"◌":latest?(latest.status==="success"?"✓":"!"):"↗";
      });
      const key=job.id+job.status;
      if(key!==lastJobKey&&job.status!=="running") {
        lastJobKey=key;
        if(job.status==="success") {
          if(job.task==="simulate")$("source").value="simulation";
          if(job.task==="experiments")$("source").value="experiments";
          if(["simulate","experiments"].includes(job.task))await loadTrajectory();
          if(job.task==="plots")$("figures").dataset.paths="";
        }
      } else lastJobKey=key;
    }
    updateSummary(state);
  } catch(error) {$("job-status").textContent="Sin conexión con el servidor local. Revisa la terminal.";}
}
$("play").addEventListener("click",()=>{if(!payload)return;if(playing){pause();return;}if(position>=1)position=0;playing=true;$("play").textContent="Ⅱ";$("play").setAttribute("aria-label","Pausar trayectoria");});
$("reset").addEventListener("click",()=>{pause();position=0;renderedIndex=-1;renderPosition();});
$("timeline").addEventListener("input",()=>{pause();position=Number($("timeline").value)/1000;renderPosition();});
for(const id of ["source","condition","seed"])$(id).addEventListener("change",loadTrajectory);
$("refresh").addEventListener("click",async()=>{await refreshState();await loadTrajectory();toast("Evidencia actualizada desde las tablas.");});
$("copy-log").addEventListener("click",async()=>{try{await navigator.clipboard.writeText($("console").textContent);toast("Salida copiada.");}catch{toast("Selecciona la salida de la consola para copiarla.");}});
async function poll(){await refreshState();setTimeout(poll,1500);}
poll();loadTrajectory();requestAnimationFrame(animate);
