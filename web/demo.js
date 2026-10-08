"use strict";
const $ = (id) => document.getElementById(id);
const providers = ["rizzo", "gemini", "liquid"];
const examples = {
  ticket: { question: "Quale reparto deve gestire il problema principale del cliente?", context: "Non riesco ad accedere al mio account dopo aver cambiato la password. Devo consegnare un lavoro entro oggi e sono completamente bloccato. L'abbonamento è attivo e il pagamento è regolare.", classes: [
    {label: "Accesso", description: "Problemi di login, password o accesso all'account."},
    {label: "Pagamenti", description: "Problemi con fatture, addebiti o abbonamenti."},
    {label: "Vendite", description: "Informazioni commerciali o acquisto di nuovi prodotti."}
  ]},
  sentiment: {question: "Qual è il sentiment della recensione?", context: "Il prodotto è arrivato in anticipo. È facile da usare, funziona benissimo e l'assistenza è stata molto disponibile. Lo consiglio!", classes: [
    {label: "Positivo", description: "Apprezzamento o soddisfazione prevalenti."},
    {label: "Neutro", description: "Descrizione senza apprezzamento o critica prevalente."},
    {label: "Negativo", description: "Critica o insoddisfazione prevalenti."}
  ]},
  document: {question: "Quale tipo di documento descrive meglio il contenuto fornito?", context: "", classes: [
    {label: "Fattura", description: "Documento che richiede il pagamento di beni o servizi."},
    {label: "Contratto", description: "Accordo che stabilisce diritti e obblighi tra le parti."},
    {label: "Curriculum", description: "Esperienze professionali e formazione di una persona."}
  ]}
};
let busy = false, attachments = [], results = {}, hasRun = false, inputChanged = false;
function node(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function getCase() {
  return {question: $("question").value.trim(), context: $("context").value.trim(),
    classes: [...document.querySelectorAll(".class-row")].map((row) => ({label: row.querySelector(".class-label").value.trim(), description: row.querySelector(".class-description").value.trim()})),
    allow_abstain: $("allow-abstain").checked};
}
function dirty() {
  if (hasRun && !busy) { inputChanged = true; $("agreement").textContent = "Input modificato · esegui un nuovo confronto"; $("agreement").className = "agreement"; }
  $("count").textContent = `${$("context").value.length.toLocaleString("it-IT")} caratteri`;
  $("request-json").textContent = JSON.stringify({...getCase(), attachments: attachments.map((file) => ({name: file.name, bytes: file.size}))}, null, 2);
}
function updateClassButtons() {
  const count = document.querySelectorAll(".class-row").length;
  $("add-class").disabled = busy || count >= 25;
  document.querySelectorAll(".class-row .remove").forEach((button) => { button.disabled = busy || count <= 2; });
}
function addClass(value = {label: "", description: ""}) {
  if (document.querySelectorAll(".class-row").length >= 25) return;
  const row = node("div", "class-row"), fields = node("div", "class-fields");
  const label = node("input", "class-label"), description = node("input", "class-description");
  Object.assign(label, {type: "text", value: value.label, placeholder: "Nome classe", maxLength: 80, required: true});
  label.setAttribute("aria-label", "Nome classe");
  Object.assign(description, {type: "text", value: value.description, placeholder: "Descrizione opzionale", maxLength: 1000});
  description.setAttribute("aria-label", "Descrizione della classe");
  fields.append(label, description);
  const remove = node("button", "remove", "×"); remove.type = "button"; remove.setAttribute("aria-label", "Rimuovi classe");
  remove.addEventListener("click", () => { if (!busy && document.querySelectorAll(".class-row").length > 2) { row.remove(); updateClassButtons(); dirty(); } });
  row.append(fields, remove); $("classes").append(row); updateClassButtons();
}
function loadExample(name) {
  if (busy) return;
  const example = examples[name]; $("question").value = example.question; $("context").value = example.context;
  $("classes").replaceChildren(); example.classes.forEach(addClass); dirty();
}
function showError(message) { $("error").textContent = message; $("error").hidden = !message; }
function renderFiles() {
  $("file-list").replaceChildren();
  attachments.forEach((file, index) => {
    const li = node("li"), remove = node("button", "remove", "×"); remove.type = "button"; remove.setAttribute("aria-label", `Rimuovi ${file.name}`);
    remove.addEventListener("click", () => { if (!busy) { attachments.splice(index, 1); renderFiles(); dirty(); } });
    li.append(node("span", "", `${file.name} · ${(file.size / 1024).toFixed(0)} KB`), remove); $("file-list").append(li);
  });
}
function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader(); reader.onload = () => resolve({name: file.name, content_base64: String(reader.result).split(",")[1]});
    reader.onerror = () => reject(new Error(`Impossibile leggere ${file.name}.`)); reader.readAsDataURL(file);
  });
}
async function post(url, body, headers = {}) {
  const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json", ...headers}, body: JSON.stringify(body), signal: AbortSignal.timeout(300000)});
  const data = await response.json();
  if (!response.ok) { let detail = data.detail; if (Array.isArray(detail)) detail = detail.map((item) => item.msg).join("; "); throw new Error(typeof detail === "string" ? detail : `Richiesta non valida (HTTP ${response.status}).`); }
  return data;
}
function metric(name, value, note) {
  const el = node("div"); el.append(node("span", "metric-name", name), node("span", "metric-value", value));
  if (note) el.append(node("p", "metric-note", note)); return el;
}
function agreement() {
  if (inputChanged) return;
  if (!providers.every((provider) => results[provider])) return;
  const accepted = new Set(["ok", "insufficient_evidence"]);
  const completed = providers.map((provider) => results[provider]).filter((result) => accepted.has(result.status));
  const partial = completed.length < providers.length;
  const match = completed.length >= 2 && completed.every((result) => result.status === completed[0].status && result.classification === completed[0].classification);
  $("agreement").textContent = completed.length < 2 ? "Confronto parziale" : `${match ? "Stessa classificazione" : "Classificazioni diverse"}${partial ? ` · ${completed.length}/3 modelli` : ""}`;
  $("agreement").className = `agreement ${completed.length < 2 ? "" : match ? "match" : "different"}`;
}
function renderProvider(provider, result) {
  const output = $(`${provider}-result`); output.replaceChildren(); output.append(node("p", "result-label", "CLASSIFICAZIONE"));
  const value = result.status === "ok" ? result.classification : result.status === "insufficient_evidence" ? "Dati insufficienti" : result.status === "uncertain" ? "Incerto" : result.status === "skipped" ? "Da configurare" : "Non completata";
  output.append(node("p", "classification", value));
  const metrics = node("div", "metrics"), cost = result.cost?.usd;
  const latency = result.latency_ms == null ? "—" : result.latency_ms < 1000 ? `${Math.round(result.latency_ms)} ms` : `${(result.latency_ms / 1000).toFixed(2)} s`;
  metrics.append(metric("TEMPO CLASSIFICAZIONE", latency), metric("COSTO API · USD", cost == null ? "—" : cost === 0 ? "$0" : `$${cost.toFixed(8)}`, result.cost?.kind === "estimated" ? "Stima dai token utilizzati" : result.cost?.kind === "free_declared" ? "Piano gratuito dichiarato" : undefined)); output.append(metrics);
  if (result.error) output.append(node("p", "provider-error", result.error));
  if (result.probabilities) {
    const top = Math.max(...result.probabilities.map((item) => item.probability));
    result.probabilities.forEach((item) => {
      const row = node("div", `bar-row${item.probability === top ? " top" : ""}`), track = node("div", "track"), fill = node("div", "fill");
      fill.style.width = `${Math.max(0, Math.min(1, item.probability)) * 100}%`; track.append(fill);
      row.append(node("span", "", item.label), track, node("span", "", `${(item.probability * 100).toFixed(1)}%`)); output.append(row);
    });
  }
  if (result.usage && provider === "gemini") output.append(node("p", "cost-note", `Token: ${result.usage.promptTokenCount ?? "—"} input · ${result.usage.candidatesTokenCount ?? "—"} risposta · ${result.usage.thoughtsTokenCount ?? 0} ragionamento.`));
  if (provider === "liquid") {
    $("liquid-model").textContent = `${result.model || $("liquid-model-select").value} · Choice`;
    if (result.usage) output.append(node("p", "cost-note", `Token: ${result.usage.input_tokens ?? "—"} input · ${result.usage.output_tokens ?? "—"} output.`));
    if (result.confidence != null) output.append(node("p", "cost-note", `Confidenza restituita da Liquid: ${(result.confidence * 100).toFixed(1)}%.`));
  }
  if (result.cost?.note) output.append(node("p", "cost-note", result.cost.note));
  $(`${provider}-card`).setAttribute("aria-busy", "false"); results[provider] = result; $("response-json").textContent = JSON.stringify(results, null, 2); agreement();
}
function setBusy(value) {
  busy = value;
  document.querySelectorAll("#compare-form input, #compare-form textarea, #compare-form select, #compare-form button, [data-example]").forEach((el) => { el.disabled = value; });
  $("run").firstElementChild.textContent = value ? "Confronto in corso…" : "Confronta i modelli"; updateClassButtons();
}
async function runProvider(provider, prepared, apiKey, tier) {
  try {
    const body = provider === "rizzo" ? prepared : provider === "gemini" ? {case: prepared, billing_tier: tier} : {case: prepared, model: tier};
    const headers = provider === "rizzo" ? {} : provider === "gemini" ? {"X-Gemini-API-Key": apiKey} : {"X-Liquid-API-Key": apiKey};
    renderProvider(provider, await post(`/api/classify/${provider}`, body, headers));
  }
  catch (error) { renderProvider(provider, {status: "error", classification: null, latency_ms: null, cost: {usd: null}, error: error.name === "TimeoutError" ? "Timeout: la richiesta può essere ancora in corso nel backend. Il costo non è determinabile." : error instanceof TypeError ? "Server locale non raggiungibile. Controlla il terminale." : error.message}); }
}
$("compare-form").addEventListener("submit", async (event) => {
  event.preventDefault(); if (busy) return;
  const input = getCase();
  if (!input.question || input.classes.some((item) => !item.label)) { showError("Inserisci una domanda e il nome di ogni classe."); return; }
  if (new Set(input.classes.map((item) => item.label.toLocaleLowerCase())).size !== input.classes.length) { showError("Le classi devono avere nomi distinti."); return; }
  const apiKey = $("api-key").value.trim(), tier = $("billing-tier").value;
  const liquidKey = $("liquid-api-key").value.trim(), liquidModel = $("liquid-model-select").value;
  showError(""); setBusy(true); results = {}; inputChanged = false;
  $("agreement").textContent = "Preparazione del contesto…"; $("agreement").className = "agreement"; $("response-json").textContent = "Confronto in corso…";
  for (const provider of providers) { $(`${provider}-result`).replaceChildren(node("p", "empty-text", "Preparazione dell'input…")); $(`${provider}-card`).setAttribute("aria-busy", "true"); }
  try {
    const prepared = await post("/api/prepare", {...input, attachments: await Promise.all(attachments.map(readFile))}); hasRun = true;
    $("request-json").textContent = JSON.stringify(prepared.case, null, 2); $("preparation").textContent = `ESTRAZIONE E PREPARAZIONE · ${Math.round(prepared.preparation_ms)} ms`;
    $("result-context").textContent = `Domanda: ${input.question} · ${prepared.files.length} file · le chiamate partono in parallelo.`; $("agreement").textContent = "Confronto in corso…";
    const pending = {rizzo: "Rizzo Flow sta valutando le classi…", gemini: apiKey ? "Gemini sta classificando il contenuto…" : "API key non impostata.", liquid: liquidKey ? "Liquid AI sta valutando le classi…" : "API key non impostata."};
    for (const provider of providers) $(`${provider}-result`).replaceChildren(node("p", "empty-text", pending[provider]));
    await Promise.all([runProvider("rizzo", prepared.case), runProvider("gemini", prepared.case, apiKey, tier), runProvider("liquid", prepared.case, liquidKey, liquidModel)]);
  } catch (error) {
    showError(error.message); $("agreement").textContent = "Input non elaborato";
    for (const provider of providers) { $(`${provider}-result`).replaceChildren(node("p", "empty-text", "Classificazione non avviata.")); $(`${provider}-card`).setAttribute("aria-busy", "false"); }
  } finally { setBusy(false); }
});
$("compare-form").addEventListener("input", (event) => {
  if (event.target.id === "api-key") $("key-state").textContent = $("api-key").value.trim() ? "API key impostata" : "API key da impostare";
  else if (event.target.id === "liquid-api-key") $("liquid-key-state").textContent = $("liquid-api-key").value.trim() ? "API key impostata" : "API key da impostare";
  else if (event.target.id !== "files") dirty();
});
$("add-class").addEventListener("click", () => { if (!busy) { addClass(); dirty(); } });
$("show-key").addEventListener("click", () => { const show = $("api-key").type === "password"; $("api-key").type = show ? "text" : "password"; $("show-key").textContent = show ? "Nascondi" : "Mostra"; $("show-key").setAttribute("aria-label", show ? "Nascondi API key" : "Mostra API key"); });
$("show-liquid-key").addEventListener("click", () => { const show = $("liquid-api-key").type === "password"; $("liquid-api-key").type = show ? "text" : "password"; $("show-liquid-key").textContent = show ? "Nascondi" : "Mostra"; $("show-liquid-key").setAttribute("aria-label", show ? "Nascondi API key Liquid" : "Mostra API key Liquid"); });
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => loadExample(button.dataset.example)));
$("files").addEventListener("change", () => {
  const candidate = [...attachments]; [...$("files").files].forEach((file) => { if (!candidate.some((item) => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) candidate.push(file); });
  if (candidate.length > 5 || candidate.some((file) => file.size > 5 * 1024 * 1024) || candidate.reduce((total, file) => total + file.size, 0) > 10 * 1024 * 1024) showError("Limite: 5 file, 5 MB per file, 10 MB totali.");
  else { attachments = candidate; showError(""); renderFiles(); dirty(); } $("files").value = "";
});
async function init() {
  loadExample("ticket");
  try {
    const response = await fetch("/health", {signal: AbortSignal.timeout(5000)}), data = await response.json();
    if (!response.ok || data.status !== "ready") throw new Error();
    $("connection").classList.add("online"); $("connection").textContent = "Rizzo Flow pronto"; $("rizzo-model").textContent = `${data.model.gguf_source || data.model.source} · ${data.model.precision} · ${data.model.device_name || data.model.backend}`;
  } catch { $("connection").textContent = "Rizzo Flow non raggiungibile"; }
  try {
    const response = await fetch("/api/config"); if (!response.ok) throw new Error(); const config = await response.json();
    $("pricing").textContent = `Standard: $${config.pricing.input_per_million_usd.toFixed(2)}/M token input · $${config.pricing.output_per_million_usd.toFixed(2)}/M output e ragionamento. Tariffe verificate ${config.pricing.checked_on}.`;
    $("liquid-pricing").textContent = `d1: $${config.liquid_pricing.input_per_million_usd.toFixed(2)}/M token input · output gratuito. d1:free: $0, se disponibile. Tariffe verificate ${config.liquid_pricing.checked_on}.`;
  } catch { $("pricing").textContent = "Tariffe non caricate. Riavvia la demo aggiornata con start.ps1."; }
}
init();
