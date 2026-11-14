// Behavioral harness for docs/app.js: runs the real script against a minimal synthetic DOM built from the real
// generated HTML (parsed by verify_site_v2.py with html.parser and passed as JSON on stdin). Pure node: no network,
// no HTTP server or listener, no files written; the pre-flight checker gets a mock fetch and the first-party beacon (docs/b.js)
// a recording navigator.sendBeacon mock. Prints one JSON object with every assertion result.
//
//   stdin: {"app": "<app.js source>", "request": <dom tree>, "index": <dom tree>, "rowId": "<a real record id>",
//           "beacon": "<b.js source>", "protocol": <dom tree of /protocols/<protocolSlug>/>, "protocolSlug": "<slug>",
//           "notfound": <dom tree of 404.html>}
//   tree node: ["tag", {attrs}, [children...]] or a text string
"use strict";
const vm = require("vm");

// ---------- strict mini selector engine (throws like a browser on malformed selectors) ----------
function parseCompound(src) {
  const c = { tag: null, id: null, classes: [], attrs: [], checked: false, not: [] };
  let i = 0;
  const ident = /^[A-Za-z_][\w-]*/;
  while (i < src.length) {
    const rest = src.slice(i);
    let m;
    if (i === 0 && (m = rest.match(/^[a-z][a-z0-9]*/))) { c.tag = m[0]; i += m[0].length; }
    else if (rest[0] === "#" && (m = rest.slice(1).match(ident))) { c.id = m[0]; i += 1 + m[0].length; }
    else if (rest[0] === "." && (m = rest.slice(1).match(ident))) { c.classes.push(m[0]); i += 1 + m[0].length; }
    else if ((m = rest.match(/^\[([\w-]+)(?:="([^"\\\]]*)")?\]/))) { c.attrs.push([m[1], m[2]]); i += m[0].length; }
    else if ((m = rest.match(/^:checked/))) { c.checked = true; i += m[0].length; }
    else if ((m = rest.match(/^:not\(([^()]+)\)/))) { c.not.push(parseCompound(m[1])); i += m[0].length; }
    else throw new SyntaxError("Failed to execute 'querySelector': '" + src + "' is not a valid selector.");
  }
  return c;
}
function parseSelector(sel) {
  if (/\\/.test(sel) || (sel.match(/\[/g) || []).length !== (sel.match(/\]/g) || []).length) {
    throw new SyntaxError("Failed to execute 'querySelector': '" + sel + "' is not a valid selector.");
  }
  return sel.split(",").map(s => s.trim().split(/\s+/).map(parseCompound));
}
function matchCompound(el, c) {
  if (!el || el.nodeType !== 1) return false;
  if (c.tag && el.tagName.toLowerCase() !== c.tag) return false;
  if (c.id && el.getAttribute("id") !== c.id) return false;
  for (const k of c.classes) if (!el.classList.contains(k)) return false;
  for (const [a, v] of c.attrs) { if (!el.hasAttribute(a)) return false; if (v !== undefined && el.getAttribute(a) !== v) return false; }
  if (c.checked && !el.checked) return false;
  for (const n of c.not) if (matchCompound(el, n)) return false;
  return true;
}
function matchChain(el, chain) {
  if (!matchCompound(el, chain[chain.length - 1])) return false;
  let i = chain.length - 2, p = el.parentNode;
  while (i >= 0 && p) { if (matchCompound(p, chain[i])) i--; p = p.parentNode; }
  return i < 0;
}
const matches = (el, list) => list.some(ch => matchChain(el, ch));

// ---------- minimal DOM ----------
class Node_ { constructor() { this.parentNode = null; this.childNodes = []; } }
class Text extends Node_ { constructor(t) { super(); this.nodeType = 3; this.data = t; } get textContent() { return this.data; } }
class ClassList {
  constructor(el) { this.el = el; }
  _get() { return (this.el.getAttribute("class") || "").split(/\s+/).filter(Boolean); }
  contains(k) { return this._get().includes(k); }
  add(k) { const s = this._get(); if (!s.includes(k)) s.push(k); this.el.setAttribute("class", s.join(" ")); }
  remove(k) { this.el.setAttribute("class", this._get().filter(x => x !== k).join(" ")); }
  toggle(k, force) { const on = force === undefined ? !this.contains(k) : !!force; on ? this.add(k) : this.remove(k); return on; }
}
class Element extends Node_ {
  constructor(tag, attrs) {
    super(); this.nodeType = 1; this.tagName = tag.toUpperCase(); this.attributes = Object.assign({}, attrs || {});
    this.style = {}; this.listeners = {}; this.classList = new ClassList(this);
    this._value = this.attributes.value !== undefined ? this.attributes.value : null;
    this._checked = "checked" in this.attributes; this._tabIndex = 0;
  }
  get checked() { return this._checked; }
  set checked(v) {   // radio-group semantics, as in a browser: checking one radio unchecks the others with its name
    this._checked = !!v;
    if (v && this.getAttribute("type") === "radio" && this.getAttribute("name")) {
      let root = this; while (root.parentNode) root = root.parentNode;
      for (const e of root._desc ? root._desc() : []) {
        if (e !== this && e.getAttribute("type") === "radio" && e.getAttribute("name") === this.getAttribute("name")) e._checked = false;
      }
    }
  }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k) ? String(this.attributes[k]) : null; }
  setAttribute(k, v) { this.attributes[k] = String(v); }
  removeAttribute(k) { delete this.attributes[k]; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attributes, k); }
  toggleAttribute(k, force) { const on = force === undefined ? !this.hasAttribute(k) : !!force; on ? this.setAttribute(k, "") : this.removeAttribute(k); return on; }
  get id() { return this.getAttribute("id") || ""; }
  get href() { return this.getAttribute("href") || ""; } set href(v) { this.setAttribute("href", v); }
  get hidden() { return this.hasAttribute("hidden"); } set hidden(v) { v ? this.setAttribute("hidden", "") : this.removeAttribute("hidden"); }
  get tabIndex() { return this._tabIndex; } set tabIndex(v) { this._tabIndex = v; }
  get value() { if (this._value !== null) return this._value; return this.tagName === "TEXTAREA" ? this.textContent : ""; }
  set value(v) { this._value = String(v); }
  get textContent() { return this.childNodes.map(c => c.textContent).join(""); }
  set textContent(v) { this.childNodes = []; if (v !== "" && v !== null && v !== undefined) this.appendChild(new Text(String(v))); }
  get innerHTML() { return this.textContent; } set innerHTML(v) { this.textContent = v; }
  get parentElement() { return this.parentNode && this.parentNode.nodeType === 1 ? this.parentNode : null; }
  appendChild(c) { if (typeof c === "string") c = new Text(c); c.parentNode = this; this.childNodes.push(c); return c; }
  remove() { if (this.parentNode) { this.parentNode.childNodes = this.parentNode.childNodes.filter(x => x !== this); this.parentNode = null; } }
  get children() { return this.childNodes.filter(c => c.nodeType === 1); }
  *_desc() { for (const c of this.children) { yield c; yield* c._desc(); } }
  querySelectorAll(sel) { const l = parseSelector(sel); return [...this._desc()].filter(e => matches(e, l)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest(sel) { const l = parseSelector(sel); let e = this; while (e && e.nodeType === 1) { if (matches(e, l)) return e; e = e.parentNode; } return null; }
  addEventListener(t, fn) { (this.listeners[t] = this.listeners[t] || []).push(fn); }
  dispatchEvent(ev) {
    ev.target = ev.target || this;
    let n = this;
    while (n && !ev._stop) { for (const fn of (n.listeners[ev.type] || []).slice()) fn.call(n, ev); n = n.parentNode; }
    return !ev.defaultPrevented;
  }
  scrollIntoView() {} focus() {} select() {}
  get elements() {
    const out = {};
    for (const e of this._desc()) { const nm = e.getAttribute("name"); if (nm && /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) && !(nm in out)) out[nm] = e; }
    return out;
  }
}
class Event_ {
  constructor(type) { this.type = type; this.defaultPrevented = false; this._stop = false; this.target = null; }
  preventDefault() { this.defaultPrevented = true; } stopPropagation() { this._stop = true; }
}
function build(tree) {
  if (typeof tree === "string") return new Text(tree);
  const [tag, attrs, kids] = tree;
  const el = new Element(tag, attrs);
  for (const k of kids) el.appendChild(build(k));
  return el;
}

// ---------- run app.js on a page ----------
function run(tree, app, loc) {
  const html = build(tree);
  const body = html.querySelector("body") || html;
  const document = new Element("#document", {});
  document.nodeType = 9; document.appendChild(html);
  document.documentElement = html; document.body = body;
  document.createElement = tag => new Element(tag, {});
  document.createTextNode = t => new Text(String(t));
  document.getElementById = id => document.querySelectorAll("[id]").find(e => e.getAttribute("id") === id) || null;
  document.execCommand = () => true;
  document.referrer = loc.referrer || "";
  html.scrollHeight = 4000;
  const winListeners = {};
  const location = { href: "https://pacta.wtf" + loc.path + (loc.search || "") + (loc.hash || ""), search: loc.search || "", hash: loc.hash || "",
    pathname: loc.path, protocol: loc.protocol || "https:", hostname: "pacta.wtf" };
  const window = {
    addEventListener: (t, fn) => { (winListeners[t] = winListeners[t] || []).push(fn); }, isSecureContext: false, location,
    scrollY: 0, innerHeight: 800
  };
  // navigator.sendBeacon is a recording mock (no network); loc.nav overrides it (e.g. doNotTrack, or no sendBeacon at all)
  const beacons = [];
  const navigator = Object.assign({ sendBeacon: (url, body) => { beacons.push({ url, body }); return true; } }, loc.nav || {});
  const ctx = {
    window, document, location, navigator, URLSearchParams, URL, AbortController: loc.noAbort ? undefined : AbortController,
    console, Promise, JSON, Date, Math,
    localStorage: { getItem: () => null, setItem: () => {} },
    setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0,
    fetch: loc.fetch || (() => Promise.reject(new Error("network disabled in harness")))
  };
  vm.createContext(ctx);
  // deferred scripts run in document order (app.js, then b.js), both before DOMContentLoaded
  if (app) vm.runInContext(app, ctx, { filename: "app.js" });
  if (loc.beacon) vm.runInContext(loc.beacon, ctx, { filename: "b.js" });
  document.dispatchEvent(new Event_("DOMContentLoaded"));
  const events = () => beacons.map(b => JSON.parse(b.body));
  return { document, window, winListeners, location, Event_, beacons, events };
}

// ---------- scenarios ----------
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const res = {};
const SCOPE = "HARNESS-SCOPE-7c1e https://example.invalid/docs 0x1111111111111111111111111111111111111111";
const TX = "0x" + "ab".repeat(32);
const FORUM = "https://forum.example.invalid/t/harness-listing/1";
const OPT = {
  clearance: "24h Collateral Onboarding & Delta Clearance Attestation ($5,000 USDC flat; optional $1,500/mo Aligned monitoring)",
  community: "Community queue (free; unscheduled, typically 6–8 weeks)"
};
function ghParams(doc) {
  const h = doc.getElementById("req-gh").getAttribute("href") || "";
  if (!/^https:\/\/github\.com\/Fractal-Neurons\/pacta\/issues\/new\?/.test(h)) return null;
  return new URLSearchParams(h.split("?")[1]);
}
function setField(doc, id, v) {
  const el = doc.getElementById(id); el.value = v;
  const ev = new Event_("input"); ev.target = el; el.dispatchEvent(ev);
}
function pick(doc, val) {
  const r = doc.querySelectorAll('input[name="tier"]').find(x => x.getAttribute("value") === val);
  r.checked = true;
  const ev = new Event_("change"); ev.target = r; r.dispatchEvent(ev);
}
const checked = doc => (doc.querySelector('input[name="tier"]:checked') || { getAttribute: () => null }).getAttribute("value");
const brief = doc => doc.getElementById("req-brief").textContent;
try {
  // (a) /request/ defaults to the 24h clearance: payment panel + tx field visible, GitHub intake prefilled with the exact dropdown option
  let p = run(input.request, input.app, { path: "/request/" });
  const d = p.document, treasury = d.getElementById("req-form").getAttribute("data-treasury");
  res.default_is_clearance = checked(d) === "clearance";
  res.clearance_pay_panel_shown = d.getElementById("req-pay").hidden === false;
  res.clearance_tx_field_shown = d.getElementById("req-tx-field").hidden === false;
  let q = ghParams(d);
  res.clearance_github_href = q !== null;
  res.clearance_github_tier_exact = !!q && q.get("package_tier") === OPT.clearance;
  res.clearance_brief_has_price_and_treasury = /\$5,000 USDC/.test(brief(d)) && /^0x[0-9a-fA-F]{40}$/.test(treasury || "") && brief(d).includes(treasury);
  // (b) a valid payment tx hash + forum URL flow into the brief and the GitHub prefill
  setField(d, "req-scope", SCOPE); setField(d, "req-forum", FORUM); setField(d, "req-tx", TX);
  q = ghParams(d);
  res.tx_valid_in_brief = brief(d).includes("Payment: " + TX) && !/\(check:/.test(brief(d));
  res.tx_valid_in_github = !!q && q.get("payment_tx_hash") === TX;
  res.forum_in_brief_and_github = brief(d).includes("Forum proposal: " + FORUM) && !!q && q.get("forum_proposal_url") === FORUM;
  res.tx_valid_not_flagged = d.getElementById("req-tx").hasAttribute("aria-invalid") === false;
  // (c) a malformed tx hash is flagged and never forwarded to GitHub
  setField(d, "req-tx", "0x1234");
  q = ghParams(d);
  res.tx_invalid_flagged = d.getElementById("req-tx").getAttribute("aria-invalid") === "true" && /\(check:/.test(brief(d));
  res.tx_invalid_not_in_github = !!q && !q.has("payment_tx_hash");
  setField(d, "req-tx", TX);
  // (d) switching to the community queue hides payment, drops the tx hash, keeps the intake link working
  pick(d, "community");
  q = ghParams(d);
  res.community_pay_panel_hidden = d.getElementById("req-pay").hidden === true;
  res.community_tx_field_hidden = d.getElementById("req-tx-field").hidden === true;
  res.community_github_tier_exact = !!q && q.get("package_tier") === OPT.community;
  res.community_no_tx_anywhere = !!q && !q.has("payment_tx_hash") && !brief(d).includes(TX) && !/Payment:/.test(brief(d));
  const ev = new Event_("click"); d.getElementById("req-gh").dispatchEvent(ev);
  res.community_click_not_prevented = ev.defaultPrevented === false;
  // (e) back to clearance restores the payment panel
  pick(d, "clearance");
  res.clearance_restores_pay_panel = d.getElementById("req-pay").hidden === false && ghParams(d).get("payment_tx_hash") === TX;
  // (f) ?tier=community prefill; unknown tiers fall back to the default
  p = run(input.request, input.app, { path: "/request/", search: "?tier=community" });
  res.prefill_selects_community = checked(p.document) === "community" && p.document.getElementById("req-pay").hidden === true;
  p = run(input.request, input.app, { path: "/request/", search: "?tier=disclosure" });
  res.prefill_unknown_tier_keeps_clearance = checked(p.document) === "clearance";
  // (g) homepage plan buttons preselect their track in #request
  p = run(input.index, input.app, { path: "/" });
  const btn = p.document.querySelectorAll("a[data-tier]").find(a => a.getAttribute("data-tier") === "community");
  const cev = new Event_("click"); btn.dispatchEvent(cev);
  res.homepage_plan_button_preselects = checked(p.document) === "community";
  // (h) malformed hashes never throw during initialization; a real id still opens its drawer
  for (const h of ["#r-[unclosed", "#r-x\\", "#r-\"]", "#r-%E0%A4%A"]) {
    try { run(input.index, input.app, { path: "/", hash: h }); res["hash_ok " + h] = true; }
    catch (e) { res["hash_ok " + h] = false; res["hash_err " + h] = String(e); }
  }
  p = run(input.index, input.app, { path: "/", hash: "#r-" + input.rowId });
  res.valid_hash_opens_drawer = p.document.getElementById("r-" + input.rowId).classList.contains("open");
  // (i0) the hero livebar names the next ETA that has not elapsed yet (tick() runs on DOMContentLoaded)
  {
    const lb = p.document.querySelector(".livebar");
    const pairs = (lb && lb.getAttribute("data-etas") || "").split(";").map((x) => x.split("|"));
    const nowS = Math.floor(Date.now() / 1000), want = pairs.find((x) => parseInt(x[0], 10) > nowS);
    const lp = lb && lb.querySelector(".lb-p"), cd = lb && lb.querySelector(".countdown"), nx = lb && lb.querySelector(".lb-next");
    res.livebar_skips_elapsed_etas = !!lb && pairs.length >= 2 && (want
      ? lp.textContent === want[1] && cd.getAttribute("data-eta") === want[0]
      : /past its ETA/.test(nx.textContent));
  }
} catch (e) {
  res.harness_error = String(e && e.stack || e);
}

// (i) live pre-flight checker: nothing is fetched on load; a preset fetches the free API exactly once; the response is
// rendered as text only (an HTML-looking summary stays text); cast commands carry the pinned block; bad input and
// HTTP errors never throw and never fetch. Mock fetch only: no network.
const PF_EXAMPLE = { schema: "pacta.preflight_check.v1", chain: "base", chainId: 8453, address: "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  pinnedBlock: 23800000, pinnedBlockHash: "0x" + "ab".repeat(32), verdict: "MULTISIG_NO_TIMELOCK", riskScore: 60, isContract: true, isProxy: true,
  implementation: "0x2222222222222222222222222222222222222222", hasAdminSlot: true, canUpgradeZeroDelay: true,
  capabilities: { pause: true, blacklist: false, upgrade: true }, paused: false,
  controller: { address: "0x3333333333333333333333333333333333333333", kind: "multisig_safe", safeThreshold: 3, timelockDelaySec: null, safeOwnerCount: 5 },
  summary: "<img src=x onerror=alert(1)> 3-of-5 Safe" };
const flush = () => new Promise(r => setImmediate(r));
async function preflightScenario() {
  const calls = [];
  let reply = { status: 200, body: PF_EXAMPLE };
  const fetchMock = (url) => {   // the inspector loads this site's own /api/v1 JSON; only API calls are counted
    if (!/\/v1\/check\/preflight/.test(String(url))) return Promise.reject(new Error("site data not needed here"));
    calls.push(String(url)); const r = reply; return Promise.resolve({ status: r.status, json: () => Promise.resolve(r.body) });
  };
  const p = run(input.index, input.app, { path: "/", fetch: fetchMock });
  const d = p.document, out = d.getElementById("pf-out"), box = d.querySelector(".pf");
  res.pf_present = !!out && !!box && /^https:\/\//.test(box.getAttribute("data-api") || "");
  res.pf_no_fetch_on_load = calls.length === 0;
  const preset = d.querySelectorAll("[data-pf-address]")[0];
  preset.dispatchEvent(new Event_("click"));
  await flush(); await flush(); await flush();
  const want = box.getAttribute("data-api") + "/v1/check/preflight?chain=" + preset.getAttribute("data-pf-chain") + "&address=" + preset.getAttribute("data-pf-address");
  res.pf_preset_fetches_once = calls.length === 1 && calls[0] === want;
  const txt = out.textContent;
  res.pf_renders_verdict = txt.includes("MULTISIG_NO_TIMELOCK") && txt.includes("Risk 60/100") && txt.includes("multisig_safe (3-of-5)") && txt.includes("pause, upgrade");
  res.pf_text_only = out.querySelectorAll("img").length === 0 && txt.includes("<img src=x onerror=alert(1)>");
  res.pf_cast_commands = txt.includes("cast storage " + PF_EXAMPLE.address + " 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --block 23800000")
    && txt.includes('"getThreshold()(uint256)" --block 23800000') && txt.includes("--rpc-url $BASE_RPC_URL");
  const form = d.getElementById("pf-form"), addr = form.querySelector('input[name="address"]');
  addr.value = "0x123"; const sev = new Event_("submit"); form.dispatchEvent(sev);
  await flush();
  res.pf_invalid_address_no_fetch = calls.length === 1 && sev.defaultPrevented === true && /40-hex/.test(out.textContent);
  reply = { status: 429, body: { error: "rate_limited", detail: "60 requests / minute" } };
  addr.value = PF_EXAMPLE.address; form.dispatchEvent(new Event_("submit"));
  await flush(); await flush(); await flush();
  res.pf_http_error_reported = calls.length === 2 && /HTTP 429 \(rate_limited\)/.test(out.textContent);
}
// (j) Codex F1 regression: a valid check is in flight, then an invalid address is submitted; the stale HTTP 200 resolves
// afterwards and must not overwrite the input error. The superseded request is aborted (AbortController).
async function staleResponseScenario() {
  const calls = [], signals = [];
  let release = null;
  const fetchMock = (url, opts) => {
    if (!/\/v1\/check\/preflight/.test(String(url))) return Promise.reject(new Error("site data not needed here"));
    calls.push(String(url)); signals.push(opts && opts.signal);
    return new Promise(r => { release = () => r({ status: 200, json: () => Promise.resolve(PF_EXAMPLE) }); });
  };
  const p = run(input.index, input.app, { path: "/", fetch: fetchMock });
  const d = p.document, out = d.getElementById("pf-out"), form = d.getElementById("pf-form"), addr = form.querySelector('input[name="address"]');
  addr.value = PF_EXAMPLE.address; form.dispatchEvent(new Event_("submit"));
  await flush();
  const pending = calls.length === 1 && /Checking/.test(out.textContent);
  addr.value = "0xnot-an-address"; form.dispatchEvent(new Event_("submit"));
  await flush();
  release(); await flush(); await flush(); await flush();
  res.pf_f1_stale_200_keeps_input_error = pending && calls.length === 1 && /40-hex/.test(out.textContent) && !out.textContent.includes("MULTISIG_NO_TIMELOCK");
  res.pf_f1_previous_request_aborted = !!signals[0] && signals[0].aborted === true;
  // same guarantee where AbortController does not exist (the sequence number alone protects the output)
  const p2 = run(input.index, input.app, { path: "/", fetch: fetchMock, noAbort: true });
  const f2 = p2.document.getElementById("pf-form"), a2 = f2.querySelector('input[name="address"]'), o2 = p2.document.getElementById("pf-out");
  a2.value = PF_EXAMPLE.address; f2.dispatchEvent(new Event_("submit")); await flush();
  a2.value = ""; f2.dispatchEvent(new Event_("submit")); await flush();
  release(); await flush(); await flush(); await flush();
  res.pf_f1_no_abortcontroller_still_safe = calls.length === 2 && signals[1] === undefined && /40-hex/.test(o2.textContent) && !o2.textContent.includes("MULTISIG_NO_TIMELOCK");
}

// (k) first-party beacon (docs/b.js) with a recording navigator.sendBeacon mock: payloads, copy hooks, scroll once, DNT,
// fetch fallback, 404, live-checker hook. Nothing leaves the process.
const BEACON = "https://pacta-x402.pacta.workers.dev/v1/telemetry/beacon";
const canon = x => Array.isArray(x) ? x.map(canon) : x && typeof x === "object" ? Object.keys(x).sort().reduce((o, k) => (o[k] = canon(x[k]), o), {}) : x;
const same = (a, b) => JSON.stringify(canon(a)) === JSON.stringify(canon(b));   // key order does not matter
function click(el) { const ev = new Event_("click"); el.dispatchEvent(ev); return ev; }
async function beaconScenario() {
  if (!input.beacon) { res.beacon_error = "no beacon source"; return; }
  const B = input.beacon;
  // page_load: referrer host + utm_source, string body to the first-party endpoint, nothing else on load
  let p = run(input.index, input.app, { path: "/", search: "?utm_source=Twitter&x=1", referrer: "https://news.ycombinator.com/item?id=1", beacon: B });
  res.b_page_load_payload = p.beacons.length === 1 && p.beacons[0].url === BEACON && typeof p.beacons[0].body === "string"
    && same(p.events()[0], { v: 1, e: "page_load", p: "/", r: "news.ycombinator.com", u: "twitter" });
  res.b_hook_exposed = typeof p.window.pactaBeacon === "function";
  // copy hooks, by what the button copies / the link points to
  const d = p.document, n0 = p.beacons.length;
  const copyMcp = d.querySelectorAll("button[data-copy]").find(b => /\/mcp$/.test(b.getAttribute("data-copy")));
  const copyCurl = d.querySelectorAll("button[data-copy]").find(b => /^curl /.test(b.getAttribute("data-copy")));
  const skill = d.querySelectorAll("a[href]").find(a => a.getAttribute("href") === "SKILL.md");
  const cta = d.querySelectorAll("a.primary")[0];
  click(copyMcp); click(copyCurl); click(skill); click(cta);
  res.b_copy_and_cta_events = same(p.events().slice(n0).map(e => e.e), ["copy_mcp_url", "copy_curl", "copy_skill_md", "cta_click"])
    && p.events().slice(n0).every(e => e.p === "/" && !("r" in e) && !("u" in e));
  // scroll_50 / scroll_90 fire once each
  const scroll = y => { p.window.scrollY = y; (p.winListeners.scroll || []).forEach(fn => fn({})); };
  const n1 = p.beacons.length;
  scroll(100); scroll(1300); scroll(1400); scroll(2900); scroll(3200); scroll(1300);
  res.b_scroll_once_each = same(p.events().slice(n1).map(e => e.e), ["scroll_50", "scroll_90"]);
  // the live checker reports chain:address (lowercased) through the hook
  const calls = [];
  const fetchMock = (url) => {
    if (!/\/v1\/check\/preflight/.test(String(url))) return Promise.reject(new Error("site data not needed here"));
    calls.push(String(url)); return Promise.resolve({ status: 200, json: () => Promise.resolve(PF_EXAMPLE) });
  };
  p = run(input.index, input.app, { path: "/", beacon: B, fetch: fetchMock });
  const f = p.document.getElementById("pf-form");
  f.querySelector('select[name="chain"]').value = "base";
  f.querySelector('input[name="address"]').value = PF_EXAMPLE.address;
  f.dispatchEvent(new Event_("submit")); await flush(); await flush(); await flush();
  const lc = p.events().filter(e => e.e === "live_checker_submit");
  res.b_live_checker_submit = lc.length === 1 && lc[0].t === "base:" + PF_EXAMPLE.address.toLowerCase() && calls.length === 1
    && p.document.getElementById("pf-out").textContent.includes("MULTISIG_NO_TIMELOCK");
  f.querySelector('input[name="address"]').value = "0x12"; f.dispatchEvent(new Event_("submit")); await flush();
  res.b_invalid_submit_not_reported = p.events().filter(e => e.e === "live_checker_submit").length === 1;
  // same-site referrer = "self"; protocol pages add t=slug and protocol_view; the term copy button = copy_curl
  if (input.protocol) {
    const path = "/protocols/" + input.protocolSlug + "/";
    p = run(input.protocol, input.app, { path, referrer: "https://pacta.wtf/protocols/", beacon: B });
    res.b_protocol_view = same(p.events(), [{ v: 1, e: "page_load", p: path, r: "self", t: input.protocolSlug }, { v: 1, e: "protocol_view", p: path, t: input.protocolSlug }]);
    const termBtn = p.document.querySelectorAll("button[data-copy-term]").find(b => /^curl /.test(b.closest(".term").querySelector("pre").textContent));
    const n2 = p.beacons.length; click(termBtn);
    const foot = p.document.querySelector(".memo-foot a"); click(foot);
    res.b_protocol_copy_curl_and_cta = same(p.events().slice(n2).map(e => e.e), ["copy_curl", "cta_click"]);
  }
  // 404: not_found_404 instead of page_load, sanitised path, slug for /protocols/<slug>/...; bad characters -> "/"
  if (input.notfound) {
    p = run(input.notfound, input.app, { path: "/protocols/no-such-protocol/extra", search: "?utm_source=newsletter", beacon: B });
    res.b_not_found_404 = same(p.events(), [{ v: 1, e: "not_found_404", p: "/protocols/no-such-protocol/extra", u: "newsletter", t: "no-such-protocol" }]);
    p = run(input.notfound, input.app, { path: "/a@b/" + "x".repeat(200), beacon: B });
    const long = run(input.notfound, input.app, { path: "/" + "y".repeat(200), beacon: B });
    res.b_not_found_path_sanitised = same(p.events(), [{ v: 1, e: "not_found_404", p: "/" }]) && long.events()[0].p === "/" + "y".repeat(119);
    const mcp = p.document.querySelectorAll("button[data-copy]").find(b => /\/mcp$/.test(b.getAttribute("data-copy")));
    if (mcp) click(mcp);
    res.b_not_found_copy_mcp = !!mcp && p.events().length === 2 && p.events()[1].e === "copy_mcp_url";
  }
  // Do Not Track: nothing at all (no beacon, no fetch), the hook stays callable; plain http (local previews): nothing
  const sent = [];
  const rec = (url, opts) => {   // records beacon traffic only; app.js's own site-data fetch (api/v1/index.json) is refused
    if (String(url) !== BEACON) return Promise.reject(new Error("site data not needed here"));
    sent.push([url, opts]); return Promise.resolve({ status: 0, type: "opaque" });
  };
  p = run(input.index, input.app, { path: "/", beacon: B, nav: { doNotTrack: "1" }, fetch: rec });
  click(p.document.querySelectorAll("button[data-copy]").find(b => /\/mcp$/.test(b.getAttribute("data-copy"))));
  p.window.scrollY = 3500; (p.winListeners.scroll || []).forEach(fn => fn({}));
  p.window.pactaBeacon("live_checker_submit", "ethereum:0x" + "1".repeat(40));
  res.b_dnt_sends_nothing = p.beacons.length === 0 && sent.length === 0 && typeof p.window.pactaBeacon === "function";
  p = run(input.index, input.app, { path: "/", beacon: B, protocol: "http:", fetch: rec });
  res.b_non_https_sends_nothing = p.beacons.length === 0 && sent.length === 0;
  // no sendBeacon: fetch keepalive no-cors with the same string body
  p = run(input.index, input.app, { path: "/", beacon: B, nav: { sendBeacon: undefined }, fetch: rec });
  await flush();
  res.b_fetch_fallback = sent.length === 1 && sent[0][0] === BEACON && sent[0][1].method === "POST" && sent[0][1].keepalive === true
    && sent[0][1].mode === "no-cors" && same(JSON.parse(sent[0][1].body), { v: 1, e: "page_load", p: "/" });
  // no cookies, no storage: the beacon run never touches document.cookie or localStorage
  let touched = false;
  const trap = { get: () => { touched = true; return ""; }, set: () => { touched = true; } };
  const t0 = run(input.index, null, { path: "/", beacon: B });   // b.js alone
  Object.defineProperty(t0.document, "cookie", trap);
  click(t0.document.querySelectorAll("button[data-copy]")[0]);
  res.b_no_cookie_access = !touched && t0.events().length >= 1;
}
(async () => {
  try { await preflightScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await staleResponseScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await beaconScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  process.stdout.write(JSON.stringify(res));
})();
