"use strict";
(() => {
  const API = "/graci/visualizer/v1";
  const SNAPSHOT_INTERVAL_MS = 3000;
  const MAX_EVENT_ROWS = 100;
  const PRESENCE_BY_STATE = Object.freeze({
    "idle":"resting", "listening":"receptive", "planning":"thinking",
    "retrieving_memory":"thinking", "reasoning":"thinking", "executing_tool":"acting",
    "testing":"validating", "reviewing":"validating", "adjudicating":"validating",
    "completed":"success", "warning":"warning", "failed":"failure", "speaking":"responding"
  });
  const SAFE_PRESENCE = "warning";
  const presenceFor = (systemState) => PRESENCE_BY_STATE[systemState] || SAFE_PRESENCE;
  const ALL_STATES = Object.freeze(Object.keys(PRESENCE_BY_STATE));
  const ALL_SEVERITIES = ["info","activity","success","warning","error"];
  const $ = (id) => document.getElementById(id);
  const state = { snapshot: null, events: new Map(), lastSuccess: 0, eventSource: null };
  const text = (value, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value).replaceAll("_", " ").toUpperCase();
  const localTime = (value, seconds = true) => { if (!value) return "—"; const date = new Date(value); return Number.isNaN(date.valueOf()) ? "—" : date.toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:seconds?"2-digit":undefined}); };
  const shortId = (value) => value ? String(value).slice(0, 14) : "—";
  const field = (root, name, value) => { const node = root.querySelector(`[data-field="${name}"]`); if (node) node.textContent = text(value); };
  function connection(kind, label) { document.body.dataset.connection = kind; const node=$("connection"); node.className=`connection ${kind}`; node.innerHTML=`<i></i> ${label}`; document.body.classList.toggle("stale", kind === "disconnected"); }
  function renderNode(id, node) {
    const root=$(id); if (!node) return; const blocked=node.node_id === "4090" && (node.eligible === false || node.mo2_state === "running");
    const available=node.endpoint_health === "healthy" && !blocked; root.dataset.status=blocked?"blocked":available?"available":node.endpoint_health === "unhealthy"?"failed":"unknown";
    root.querySelector(".availability").textContent=blocked?"BLOCKED — MO2 RUNNING":available?"AVAILABLE / HEALTHY":text(node.availability);
    field(root,"health",node.endpoint_health); field(root,"model",node.assigned_model,"UNASSIGNED"); field(root,"role",node.assigned_role || node.role); field(root,"mo2",node.mo2_state,"NOT OBSERVED"); field(root,"eligibility",node.eligible===true?"ELIGIBLE":node.eligible===false?"BLOCKED":"UNKNOWN"); field(root,"reason",node.policy_reason,"NO POLICY RESTRICTION");
  }
  function renderAgent(id, agent) { const root=$(id); if(!agent)return; field(root,"model",agent.model_id); field(root,"activity",agent.activity || agent.review_status || agent.state); root.dataset.status=agent.state; }
  function setStage(name,status,label) { const root=document.querySelector(`[data-stage="${name}"]`); if(!root)return; root.dataset.status=status; root.querySelector("b").textContent=text(label || status); }
  function renderPipeline(s) {
    const active=s.system_state; const memory=s.memory.requested ? (active==="retrieving_memory"?"active":s.memory.supplied_memory_ids.length?"passed":"pending") : "not_applicable";
    const ops=s.execution.operations||[]; const opFailed=ops.some(x=>x.status==="failed"); const opActive=ops.some(x=>x.status==="active");
    setStage("memory",memory); setStage("qwen",s.agents.qwen.state,s.agents.qwen.activity||s.agents.qwen.state); setStage("tools",opFailed?"failed":opActive||active==="executing_tool"?"active":ops.length?"passed":"not_applicable"); setStage("tests",s.execution.tests.status); setStage("review",s.review.reviewer_status); setStage("adjudication",s.review.adjudication_status);
  }
  function renderSnapshot(s) {
    state.snapshot=s; state.lastSuccess=Date.now(); connection("live","LIVE"); const presence=presenceFor(s.system_state); document.body.dataset.systemState=ALL_STATES.includes(s.system_state)?s.system_state:"warning"; document.body.dataset.presence=presence;
    $("overall-state").textContent=text(s.system_state,"UNKNOWN"); $("core-state").textContent=text(s.system_state,"UNKNOWN"); $("presence-category").textContent=text(presence); $("schema").textContent=`v${s.schema_version}`; $("snapshot-id").textContent=shortId(s.snapshot_id); $("updated").textContent=localTime(s.generated_at); $("freshness").textContent="LIVE OBSERVED STATE";
    renderNode("node-3090",s.compute.primary_3090); renderNode("node-4090",s.compute.optional_4090); renderAgent("agent-qwen",s.agents.qwen); renderAgent("agent-glm",s.agents.glm);
    const task=s.task, hasTask=Boolean(task.task_id); $("task-summary").textContent=hasTask?(task.summary||"BOUNDED TASK"):"SYSTEM AT REST"; $("task-id").textContent=shortId(task.task_id); $("task-phase").textContent=text(task.phase,hasTask?text(s.system_state):"IDLE"); $("task-started").textContent=localTime(task.started_at);
    const pct=task.progress_total?Math.min(100,Math.round(task.progress_current/task.progress_total*100)):0; $("task-progress").style.width=`${pct}%`; $("task-status").textContent=task.failure_reason|| (hasTask?`${text(task.final_status)} · ${pct}% observed progress`:"No current task. Monitoring local runtime.");
    const m=s.memory; document.querySelector(".memory-panel").classList.toggle("active",m.requested); $("memory-status").textContent=text(m.selection_status,m.requested?"REQUESTED":"N/A"); $("memory-mode").textContent=text(m.mode); $("memory-keys").textContent=m.relevance_keys.length; $("memory-selected").textContent=m.selected_memory_ids.length; $("memory-supplied").textContent=m.supplied_memory_ids.length; $("memory-context").textContent=Number(m.context_characters).toLocaleString(); $("memory-diag").textContent=`${m.conflict_count} / ${m.corruption_count}`;
    const review=$("review-panel"), adjudication=$("adjudication-panel"); review.querySelector("strong").textContent=text(s.review.structured_verdict||s.review.reviewer_status); review.dataset.status=s.review.reviewer_status; adjudication.querySelector("strong").textContent=text(s.review.final_outcome||s.review.adjudication_status); adjudication.dataset.status=s.review.adjudication_status;
    renderPipeline(s); renderOperations(s.execution.operations||[]); (s.recent_events||[]).forEach(addEvent); renderEvents();
  }
  function renderOperations(ops) { const root=$("operations"); const rows=ops.slice(-12).reverse(); root.innerHTML=rows.length?rows.map(op=>`<div class="operation" data-status="${op.status}"><b>${text(op.category)}</b><span>${escapeHtml(op.target_label||"BOUNDED OPERATION")}</span><em>${text(op.status)}</em></div>`).join(""):'<p class="empty">No execution operations observed.</p>'; }
  function escapeHtml(value) { const e=document.createElement("span"); e.textContent=String(value); return e.innerHTML; }
  function addEvent(event) { if(!event||!event.event_id||!ALL_SEVERITIES.includes(event.severity)||state.events.has(event.event_id))return; state.events.set(event.event_id,event); while(state.events.size>MAX_EVENT_ROWS)state.events.delete(state.events.keys().next().value); }
  function renderEvents() { const values=[...state.events.values()].slice(-MAX_EVENT_ROWS).reverse(); $("event-count").textContent=`${values.length} / ${MAX_EVENT_ROWS}`; $("events").innerHTML=values.length?values.map(e=>`<div class="event" data-severity="${e.severity}"><time title="${escapeHtml(e.timestamp)}">${localTime(e.timestamp)}</time><b>${text(e.event_type)}</b><small>${text(e.source)}</small><span>${escapeHtml(e.message)}</span></div>`).join(""):'<p class="empty">Waiting for trusted local events…</p>'; }
  async function getJson(path) { const response=await fetch(path,{cache:"no-store",headers:{"Accept":"application/json"}}); if(!response.ok)throw new Error(`HTTP ${response.status}`); return response.json(); }
  async function refreshSnapshot() { try { await getJson(`${API}/health`); renderSnapshot(await getJson(`${API}/snapshot`)); } catch { markDisconnected(); } }
  async function refreshEvents() { try { (await getJson(`${API}/events`)).forEach(addEvent); renderEvents(); } catch { markDisconnected(); } }
  function markDisconnected() { connection("disconnected","DISCONNECTED"); if(state.snapshot){const age=Math.max(0,Math.floor((Date.now()-state.lastSuccess)/1000)); $("freshness").textContent=`STALE · ${age}s SINCE UPDATE`;} }
  function connectEvents() { if(state.eventSource)state.eventSource.close(); const source=new EventSource(`${API}/events/stream`); state.eventSource=source; source.onopen=()=>{connection("live","LIVE"); refreshSnapshot();}; source.onerror=()=>markDisconnected(); ALL_STATES.forEach(()=>{}); source.onmessage=consume; ["system_ready","system_idle","task_started","task_completed","task_failed","route_selected","route_fallback","node_ineligible","mo2_running","endpoint_unhealthy","qwen_started","qwen_completed","glm_started","glm_completed","memory_requested","memory_selected","no_applicable_memory","memory_conflict","memory_unavailable","tool_started","tool_completed","tool_failed","tests_started","tests_passed","tests_failed","review_started","review_completed","adjudication_completed"].forEach(type=>source.addEventListener(type,consume)); }
  function consume(message) { try { const event=JSON.parse(message.data); addEvent(event); renderEvents(); if(["task_started","task_completed","task_failed","mo2_running","tests_passed","tests_failed","review_completed","adjudication_completed"].includes(event.event_type))refreshSnapshot(); } catch { /* malformed observer data is ignored */ } }
  function tick() { $("clock").textContent=new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}); if(document.body.dataset.connection==="disconnected"&&state.lastSuccess)markDisconnected(); }
  async function start() { tick(); setInterval(tick,1000); await Promise.allSettled([refreshSnapshot(),refreshEvents()]); connectEvents(); setInterval(refreshSnapshot,SNAPSHOT_INTERVAL_MS); }
  start();
})();
