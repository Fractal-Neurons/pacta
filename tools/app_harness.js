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
  get firstChild() { return this.childNodes[0] || null; }
  contains(n) { for (let e = n; e; e = e.parentNode) if (e === this) return true; return false; }
  insertBefore(c, ref) { if (typeof c === "string") c = new Text(c); c.parentNode = this; const i = this.childNodes.indexOf(ref); if (i < 0) this.childNodes.push(c); else this.childNodes.splice(i, 0, c); return c; }
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
const INIT_ERRORS = [];   // every run except the deliberate breakTheme one must start without an init error
function run(tree, app, loc) {
  const html = build(tree);
  const body = html.querySelector("body") || html;
  const document = new Element("#document", {});
  document.nodeType = 9; document.appendChild(html);
  document.documentElement = html; document.body = body;
  document.createElement = tag => new Element(tag, {});
  document.createElementNS = (ns, tag) => new Element(tag, {});   // SVG rosettes (namespace irrelevant in the synthetic DOM)
  document.createTextNode = t => new Text(String(t));
  document.getElementById = id => document.querySelectorAll("[id]").find(e => e.getAttribute("id") === id) || null;
  document.execCommand = () => true;
  document.referrer = loc.referrer || "";
  html.scrollHeight = 4000;
  const winListeners = {}, zero = [];
  if (loc.breakTheme) html.classList.toggle = () => { throw new Error("simulated early init failure (theme)"); };
  const host = loc.hostname || "pacta.wtf";
  const location = { href: "https://" + host + loc.path + (loc.search || "") + (loc.hash || ""), search: loc.search || "", hash: loc.hash || "",
    pathname: loc.path, protocol: loc.protocol || "https:", hostname: host };
  const history = {
    replaceState: (_s, _t, u) => {
      try {
        const parsed = new URL(String(u), "https://" + host);
        location.pathname = parsed.pathname;
        location.search = parsed.search;
        location.hash = parsed.hash;
        location.href = parsed.href;
      } catch (_) {}
    }
  };
  const window = {
    addEventListener: (t, fn) => { (winListeners[t] = winListeners[t] || []).push(fn); }, isSecureContext: false, location, history,
    scrollY: 0, innerHeight: 800
  };
  Object.assign(window, loc.win || {});
  location.replace = (u) => { location.replaced = String(u); };   // v2: the /request/ ?tier= forward   // v5.0: window.ethereum (checkout wallet mock), pactaRescued (404 rescue)
  // navigator.sendBeacon is a recording mock (no network); loc.nav overrides it (e.g. doNotTrack, or no sendBeacon at all)
  const beacons = [];
  const navigator = Object.assign({ sendBeacon: (url, body) => { beacons.push({ url, body }); return true; } }, loc.nav || {});
  const ctx = {
    window, document, location, navigator, URLSearchParams, URL, AbortController: loc.noAbort ? undefined : AbortController,
    console, Promise, JSON, Date, Math, Event: Event_,
    localStorage: loc.storage || { getItem: () => null, setItem: () => {}, removeItem: () => {} },
    setTimeout: loc.setTimeout || ((fn, ms) => { if (!ms && typeof fn === "function") zero.push(fn); return 0; }),
    clearTimeout: loc.clearTimeout || (() => {}), setInterval: () => 0,
    fetch: loc.fetch || (() => Promise.reject(new Error("network disabled in harness")))
  };
  vm.createContext(ctx);
  // deferred scripts run in document order (app.js, then b.js), both before DOMContentLoaded
  if (app) vm.runInContext(app, ctx, { filename: "app.js" });
  if (loc.beacon) vm.runInContext(loc.beacon, ctx, { filename: "b.js" });
  document.dispatchEvent(new Event_("DOMContentLoaded"));
  const initErrors = [];   // v4.3: errors an isolated init re-threw asynchronously (setTimeout(fn, 0))
  zero.splice(0).forEach((fn) => { try { fn(); } catch (e) { initErrors.push(String(e && e.message || e)); } });
  if (!loc.breakTheme) INIT_ERRORS.push(...initErrors);
  const events = () => beacons.map(b => JSON.parse(b.body));
  return { document, window, winListeners, location, Event_, beacons, events, initErrors };
}

// ---------- scenarios ----------
const input = JSON.parse(require("fs").readFileSync(0, "utf8"));
const res = {};
const SCOPE = "HARNESS-SCOPE-7c1e https://example.invalid/docs 0x1111111111111111111111111111111111111111";
const TX = "0x" + "ab".repeat(32);
const FORUM = "https://forum.example.invalid/t/harness-listing/1";
const OPT = {
  clearance: "Full Protocol Control-Plane Dossier ($2,500–$5,000 USDC, 24h SLA)",
  wholesale: "Wholesale Ecosystem & Curator Vault Sweep ($150 per protocol)",
  continuous: "Continuous Control-Plane Monitoring ($500–$2,500 USDC per month)",
  api_sla: "Enterprise / High-Throughput API SLA (priced on scope)",
  community: "Free factual re-verification within 7 days (merged docs or on-chain fix)"
};
const SET = { invoice: "Option A: formal commercial invoice (PDF) and counterparty settlement", direct: "Option B: direct on-chain USDC settlement" };
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
const settled = doc => (doc.querySelector('input[name="settlement"]:checked') || { getAttribute: () => null }).getAttribute("value");
function settle(doc, val) {
  const r = doc.querySelectorAll('input[name="settlement"]').find(x => x.getAttribute("value") === val);
  r.checked = true;
  const ev = new Event_("change"); ev.target = r; r.dispatchEvent(ev);
}
const brief = doc => doc.getElementById("req-brief").textContent;
try {
  // (a) /request/ defaults to the 24h clearance settled by Option A (commercial invoice): settlement panel visible,
  //     tx field and direct-settlement address hidden, GitHub intake prefilled with the exact dropdown options
  let p = run(input.request, input.app, { path: "/request/" });
  const d = p.document, treasury = d.getElementById("req-form").getAttribute("data-treasury");
  res.default_is_clearance = checked(d) === "clearance";
  const sub = new Event_("submit");
  res.req_form_submit_prevented = d.getElementById("req-form").dispatchEvent(sub) === false && sub.defaultPrevented === true
    && !d.getElementById("req-form").hasAttribute("onsubmit");
  res.default_settlement_is_invoice = settled(d) === "invoice";
  res.clearance_pay_panel_shown = d.getElementById("req-pay").hidden === false;
  res.invoice_hides_tx_and_direct = d.getElementById("req-tx-field").hidden === true && d.getElementById("req-direct").hidden === true;
  let q = ghParams(d);
  res.clearance_github_href = q !== null;
  res.clearance_github_tier_exact = !!q && q.get("package_tier") === OPT.clearance && q.get("settlement_preference") === SET.invoice;
  res.clearance_brief_has_price_and_invoice = /\$5,000 USDC/.test(brief(d)) && brief(d).includes("Settlement: Option A") && !brief(d).includes("Payment:")
    && /^0x[0-9a-fA-F]{40}$/.test(treasury || "") && !brief(d).includes(treasury);
  res.pay_summary_tracks_tier = d.getElementById("req-pay-sum").textContent === "Full Protocol Control-Plane Dossier · $2,500–$5,000 USDC, 24h SLA";
  // (b) Option B (direct on-chain USDC): tx field + treasury shown; a valid tx hash + forum URL flow into the brief and the GitHub prefill
  settle(d, "direct");
  res.direct_shows_tx_and_treasury = d.getElementById("req-tx-field").hidden === false && d.getElementById("req-direct").hidden === false
    && brief(d).includes("Settlement: Option B") && brief(d).includes(treasury) && brief(d).includes("Pacta treasury (direct settlement EOA)")
    && !/\bSafe\b|multisig/i.test(brief(d));
  setField(d, "req-scope", SCOPE); setField(d, "req-forum", FORUM); setField(d, "req-tx", TX);
  q = ghParams(d);
  res.tx_valid_in_brief = brief(d).includes("Payment: " + TX) && !/\(check:/.test(brief(d));
  res.tx_valid_in_github = !!q && q.get("payment_tx_hash") === TX && q.get("settlement_preference") === SET.direct;
  res.forum_in_brief_and_github = brief(d).includes("Forum proposal: " + FORUM) && !!q && q.get("forum_proposal_url") === FORUM;
  res.tx_valid_not_flagged = d.getElementById("req-tx").hasAttribute("aria-invalid") === false;
  // (c) a malformed tx hash is flagged and never forwarded to GitHub
  setField(d, "req-tx", "0x1234");
  q = ghParams(d);
  res.tx_invalid_flagged = d.getElementById("req-tx").getAttribute("aria-invalid") === "true" && /\(check:/.test(brief(d));
  res.tx_invalid_not_in_github = !!q && !q.has("payment_tx_hash");
  setField(d, "req-tx", TX);
  // (c2) back to Option A drops the tx hash from the brief and the intake (it stays in the field)
  settle(d, "invoice");
  q = ghParams(d);
  res.invoice_drops_tx = !brief(d).includes(TX) && !!q && !q.has("payment_tx_hash") && d.getElementById("req-tx").value === TX;
  settle(d, "direct");
  // (d) switching to the community queue hides payment, drops the tx hash, keeps the intake link working
  pick(d, "community");
  q = ghParams(d);
  res.community_pay_panel_hidden = d.getElementById("req-pay").hidden === true;
  res.community_tx_field_hidden = d.getElementById("req-tx-field").hidden === true;
  res.community_github_tier_exact = !!q && q.get("package_tier") === OPT.community && !q.has("settlement_preference");
  res.community_no_tx_anywhere = !!q && !q.has("payment_tx_hash") && !brief(d).includes(TX) && !/Payment:|Settlement:/.test(brief(d));
  const ev = new Event_("click"); d.getElementById("req-gh").dispatchEvent(ev);
  res.community_click_not_prevented = ev.defaultPrevented === false;
  // (e) back to clearance restores the payment panel (Option B still chosen, so the tx hash returns)
  pick(d, "clearance");
  res.clearance_restores_pay_panel = d.getElementById("req-pay").hidden === false && ghParams(d).get("payment_tx_hash") === TX;
  // (e2) continuous and API SLA tracks: own dropdown option, own amount in the summary and the Option B payment line
  pick(d, "continuous");
  q = ghParams(d);
  res.continuous_track = q.get("package_tier") === OPT.continuous && brief(d).includes("$500–$2,500 USDC per month in USDC to the Pacta treasury")
    && d.getElementById("req-pay-sum").textContent === "Continuous Control-Plane Monitoring · $500–$2,500 USDC per month";
  pick(d, "api_sla");
  q = ghParams(d);
  res.api_sla_track = q.get("package_tier") === OPT.api_sla && d.getElementById("req-pay").hidden === false
    && d.getElementById("req-pay-sum").textContent === "Enterprise / High-Throughput API SLA · priced on scope";
  // (f) ?tier=community prefill; ?tier=wholesale-150 prefill; legacy ?tier=rapid-500 forwards to free 7-day community track; unknown tiers fall back to default
  p = run(input.request, input.app, { path: "/request/", search: "?tier=community" });
  res.prefill_selects_community = checked(p.document) === "community" && p.document.getElementById("req-pay").hidden === true;
  p = run(input.request, input.app, { path: "/request/", search: "?tier=disclosure" });
  res.prefill_unknown_tier_keeps_clearance = checked(p.document) === "clearance";
  const pw = run(input.request, input.app, { path: "/request/", search: "?tier=wholesale-150" });
  p = run(input.request, input.app, { path: "/request/", search: "?tier=rapid-500" });
  res.prefill_rapid_500 = checked(pw.document) === "wholesale-150" && pw.document.getElementById("req-pay").hidden === false
    && ghParams(pw.document) !== null && ghParams(pw.document).get("package_tier") === OPT.wholesale
    && checked(p.document) === "community" && p.document.getElementById("req-pay").hidden === true
    && ghParams(p.document) !== null && ghParams(p.document).get("package_tier") === OPT.community;
  // (f2) /request/?tier=…&protocol=…&forum=…&settlement=… prefill (the conversion-card links)
  {
    const PF = "https://forum.example.invalid/t/listing-proposal/42";
    const fieldVal = (doc, id) => doc.getElementById(id).value;
    // v4: the protocols in scope are a Command combobox (role=option, aria-selected) instead of 86 checkboxes
    const box = (doc, slug) => doc.querySelectorAll('[role="option"]').find(x => x.getAttribute("data-slug") === slug);
    const slug = input.prefillSlug, name = box(d, slug) && box(d, slug).getAttribute("data-name");
    let x = run(input.request, input.app, { path: "/request/", search: "?tier=clearance&protocol=" + slug + "&forum=" + encodeURIComponent(PF) });
    let xd = x.document, xq = ghParams(xd);
    res.prefill_clearance_protocol_forum = checked(xd) === "clearance" && settled(xd) === "invoice" && !!name && box(xd, slug).getAttribute("aria-selected") === "true"
      && fieldVal(xd, "req-org") === name && fieldVal(xd, "req-forum") === PF && brief(xd).includes("Protocols in scope: " + name)
      && brief(xd).includes("Forum proposal: " + PF) && xq.get("forum_proposal_url") === PF && xq.get("settlement_preference") === SET.invoice;
    x = run(input.request, input.app, { path: "/request/", search: "?tier=clearance&protocol=" + slug + "&forum=" + encodeURIComponent(PF) + "&settlement=direct" });
    xd = x.document;
    res.prefill_settlement_direct = settled(xd) === "direct" && xd.getElementById("req-tx-field").hidden === false
      && xd.getElementById("req-direct").hidden === false && brief(xd).includes("Settlement: Option B");
    x = run(input.request, input.app, { path: "/request/", search: "?tier=continuous&protocol=" + slug + "&settlement=invoice" });
    xd = x.document; xq = ghParams(xd);
    res.prefill_continuous_invoice = checked(xd) === "continuous" && settled(xd) === "invoice" && xq.get("package_tier") === OPT.continuous
      && xq.get("settlement_preference") === SET.invoice && fieldVal(xd, "req-forum") === "";
    x = run(input.request, input.app, { path: "/request/", search: "?tier=api_sla" });
    res.prefill_api_sla = checked(x.document) === "api_sla" && x.document.getElementById("req-pay").hidden === false;
    // an issuer slug that is not an indexed protocol (e.g. an onboarding brief) only fills the organisation field
    x = run(input.request, input.app, { path: "/request/", search: "?tier=clearance&protocol=kerne-kusd-base" });
    res.prefill_unknown_slug_text_only = fieldVal(x.document, "req-org") === "kerne-kusd-base"
      && x.document.querySelectorAll('input[name="protocol"]').every(b => b.checked === false);
    // hostile input: unknown / prototype enum values ignored; markup stays text; control and bidi characters stripped; length capped
    const evil = "<img src=x onerror=alert(1)>" + String.fromCharCode(0, 7, 0x202e, 0x2066, 0x200b) + "x".repeat(200);
    x = run(input.request, input.app, { path: "/request/", search: "?tier=constructor&settlement=__proto__&protocol=" + encodeURIComponent(evil) + "&forum=" + encodeURIComponent("javascript:alert(1)") });
    xd = x.document;
    const org = fieldVal(xd, "req-org");
    res.prefill_hostile_inert = checked(xd) === "clearance" && settled(xd) === "invoice" && org.length === 80 && org.startsWith("<img src=x onerror=alert(1)>xxx")
      && !/[\u0000-\u001f\u202e\u2066\u200b]/.test(org) && fieldVal(xd, "req-forum") === ""
      && xd.querySelectorAll("img").length === d.querySelectorAll("img").length && !xd.querySelectorAll("img").some(i => i.getAttribute("onerror") !== null)
      && brief(xd).includes("Organization: <img src=x onerror=alert(1)>");
    for (const tier of ["__proto__", "toString", "hasOwnProperty", "TIER", "clearance%00", ""]) {
      x = run(input.request, input.app, { path: "/request/", search: "?tier=" + tier + "&settlement=" + tier });
      if (checked(x.document) !== "clearance" || settled(x.document) !== "invoice") res.prefill_enum_closed = false;
    }
    if (res.prefill_enum_closed !== false) res.prefill_enum_closed = true;
    const badForums = ["http://forum.example.invalid/t/1", "https://user:pw@forum.example.invalid/t/1", "https://:pw@forum.example.invalid/",
      "https://forum.example.invalid/" + "a".repeat(300), "https://forum.example.invalid/t 1", "data:text/html,hi", "//forum.example.invalid/t/1", "https:"];
    res.prefill_forum_https_only = badForums.every(f => fieldVal(run(input.request, input.app, { path: "/request/", search: "?forum=" + encodeURIComponent(f) }).document, "req-forum") === "");
  }
  p = run(input.index, input.app, { path: "/" });
  // (h) malformed hashes never throw during initialization; a real id still opens its drawer
  for (const h of ["#r-[unclosed", "#r-x\\", "#r-\"]", "#r-%E0%A4%A"]) {
    try { run(input.index, input.app, { path: "/", hash: h }); res["hash_ok " + h] = true; }
    catch (e) { res["hash_ok " + h] = false; res["hash_err " + h] = String(e); }
  }
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
  const want = box.getAttribute("data-api") + "/v1/check/preflight?chain=" + preset.getAttribute("data-pf-chain") + "&address=" + preset.getAttribute("data-pf-address")
    + "&caller_agent=pacta-wtf-checker&requester_role=individual_user&caller_purpose=general_research";
  res.pf_preset_fetches_once = calls.length === 1 && calls[0] === want;
  const txt = out.textContent;
  res.pf_renders_verdict = txt.includes("MULTISIG_NO_TIMELOCK") && txt.includes("Heuristic score") && txt.includes("60/100") && txt.includes("Safe multisig (3-of-5)") && txt.includes("pause, upgrade");
  // V05 + F05: plain-English verdict with the raw enum / JSON one click away; live contract check vs pinned comparison; 1-click RPC verify
  // v4 (U5): verdict first, then score / confidence / scope, then facts; cast + raw JSON in collapsed accordion items
  res.pp2_verdict_plain = txt.includes("A multisig can change it with no delay") && !!out.querySelector("[data-pf-scope]") && !!out.querySelector("[data-pf-raw]")
    && out.querySelector("[data-pf-raw]").getAttribute("open") === null
    && out.querySelector("[data-pf-raw]").textContent.includes("MULTISIG_NO_TIMELOCK") && txt.includes("Live contract check")
    && !!out.querySelector("[data-live-verify-btn]") && txt.includes('"getOwners()(address[])"') && txt.includes("--field hash");
  res.pf_text_only = out.querySelectorAll("img").length === 0 && txt.includes("<img src=x onerror=alert(1)>");
  res.pf_cast_commands = txt.includes("cast storage " + PF_EXAMPLE.address + " 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --block 23800000")
    && txt.includes('"getThreshold()(uint256)" --block 23800000') && txt.includes("--rpc-url $BASE_RPC_URL");
  const form = d.getElementById("pf-form"), addr = form.querySelector('input[name="address"]');
  addr.value = "0x123"; const sev = new Event_("submit"); form.dispatchEvent(sev);
  await flush();
  const perr = d.getElementById("pf-addr-error");   // U3: the error sits under the field, not in the result area
  res.pf_invalid_address_no_fetch = calls.length === 1 && sev.defaultPrevented === true && /40 hexadecimal/.test(perr.textContent) && perr.hidden === false;
  reply = { status: 429, body: { error: "rate_limited", detail: "60 requests / minute" } };
  addr.value = PF_EXAMPLE.address; form.dispatchEvent(new Event_("submit"));
  await flush(); await flush(); await flush();
  res.pf_http_error_reported = calls.length === 2 && /HTTP 429 \(rate_limited\)/.test(out.textContent)
    && !!out.querySelector('[data-pf-state="ratelimit"]') && !!out.querySelector("[data-pf-retry]");
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
  const perr = d.getElementById("pf-addr-error");
  res.pf_f1_stale_200_keeps_input_error = pending && calls.length === 1 && /40 hexadecimal/.test(perr.textContent) && perr.hidden === false
    && !out.textContent.includes("MULTISIG_NO_TIMELOCK");
  res.pf_f1_previous_request_aborted = !!signals[0] && signals[0].aborted === true;
  // same guarantee where AbortController does not exist (the sequence number alone protects the output)
  const p2 = run(input.index, input.app, { path: "/", fetch: fetchMock, noAbort: true });
  const f2 = p2.document.getElementById("pf-form"), a2 = f2.querySelector('input[name="address"]'), o2 = p2.document.getElementById("pf-out");
  a2.value = PF_EXAMPLE.address; f2.dispatchEvent(new Event_("submit")); await flush();
  a2.value = ""; f2.dispatchEvent(new Event_("submit")); await flush();
  release(); await flush(); await flush(); await flush();
  const e2 = p2.document.getElementById("pf-addr-error");
  res.pf_f1_no_abortcontroller_still_safe = calls.length === 2 && signals[1] === undefined && /Enter a contract address/.test(e2.textContent) && e2.hidden === false
    && !o2.textContent.includes("MULTISIG_NO_TIMELOCK");
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
    && same(p.events()[0], { v: 1, h: "wtf", e: "page_load", p: "/", r: "news.ycombinator.com", u: "twitter" });
  res.b_hook_exposed = typeof p.window.pactaBeacon === "function";
  // copy hooks, by what the button copies / the link points to
  const d = p.document, n0 = p.beacons.length;
  // v4: the homepage quickstarts are Tabs of code blocks (data-copy-term); the CTA is a default-variant Button link
  const termCopy = (re) => d.querySelectorAll("button[data-copy-term]").find(b => re.test((b.closest(".term").querySelector("pre") || { textContent: "" }).textContent));
  const copyMcp = termCopy(/\/mcp$/);
  const copyCurl = termCopy(/^curl /);
  const skill = d.querySelectorAll("a[href]").find(a => a.getAttribute("href") === "SKILL.md");
  const cta = d.querySelectorAll('a[data-variant="default"]')[0];
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
    res.b_protocol_view = same(p.events(), [{ v: 1, h: "wtf", e: "page_load", p: path, r: "self", t: input.protocolSlug }, { v: 1, e: "protocol_view", p: path, t: input.protocolSlug }]);
    const termBtn = p.document.querySelectorAll("button[data-copy-term]").find(b => /^curl /.test(b.closest(".term").querySelector("pre").textContent));
    const n2 = p.beacons.length; click(termBtn);
    const foot = p.document.querySelector(".memo-foot a"); click(foot);
    res.b_protocol_copy_curl_and_cta = same(p.events().slice(n2).map(e => e.e), ["copy_curl", "cta_click"]);
    // conversion callouts: every data-cta link (aligned page: maintenance + invoice; delta / RPC-observed page and briefs:
    // clearance + commercial invoice) fires cta_click
    const ctaClicks = (tree, path) => {
      const q = run(tree, input.app, { path, beacon: B }), links = q.document.querySelectorAll("a[data-cta]"), n = q.beacons.length;
      links.forEach(click);
      return { kinds: links.map(a => a.getAttribute("data-cta")), events: q.events().slice(n).map(e => e.e) };
    };
    const al = ctaClicks(input.protocol, path);
    res.b_cta_aligned_maintenance = same(al.kinds, ["continuous", "continuous_invoice"]) && same(al.events, ["cta_click", "cta_click"]);
    if (input.clearanceProtocol) {
      const cl = ctaClicks(input.clearanceProtocol, "/protocols/" + input.clearanceSlug + "/");
      res.b_cta_clearance_protocol = same(cl.kinds, ["sponsor_pool", "scan_free", "free_notify", "clearance", "clearance_invoice"])
        && same(cl.events, ["cta_click", "cta_click", "cta_click", "cta_click", "cta_click"]);
    }
    if (input.brief) {
      const br = ctaClicks(input.brief, "/briefs/" + input.briefSlug + "/");
      res.b_cta_clearance_brief = same(br.kinds, ["free_notify", "clearance", "clearance_invoice"]) && same(br.events, ["cta_click", "cta_click", "cta_click"]);
    }
    const hp = ctaClicks(input.index, "/");
    res.b_cta_pricing = same(hp.kinds, ["pricing_scan_free", "pricing_mcp", "pricing_sponsor_pool", "pricing_wholesale", "pricing_watch_pilot",
                                        "pricing_radar", "pricing_clearance", "pricing_wholesale_150", "pricing_continuous", "pricing_community", "pricing_api_sla"])
      && hp.events.length === 11 && hp.events.every((e) => e === "cta_click");
  }
  // 404: not_found_404 instead of page_load; paths are redacted to a closed canonical set BEFORE transmission
  // (Phase C.1): only /protocols/<safe-slug>/ keeps its slug (and t); anything else is "/404"; IP / local referrers are dropped
  if (input.notfound) {
    p = run(input.notfound, input.app, { path: "/protocols/pendle-finance-v2", search: "?utm_source=newsletter", referrer: "https://github.com/x/y?z=1", beacon: B });
    res.b_not_found_404 = same(p.events(), [{ v: 1, h: "wtf", e: "not_found_404", p: "/404", r: "github.com", u: "newsletter" }]);   // Phase C.2: every 404 is "/404", never a slug
    const spec = run(input.notfound, input.app, { path: "/reset/alice%40example.org/private-token", referrer: "https://192.0.2.44/secret", beacon: B });
    const spec2 = run(input.notfound, input.app, { path: "/protocols/pendle-finance-v2", referrer: "https://github.com/some/repo", beacon: B });
    res.b_c1_spec_payloads = same(spec.events(), [{ v: 1, h: "wtf", e: "not_found_404", p: "/404" }])
      && same(spec2.events(), [{ v: 1, h: "wtf", e: "not_found_404", p: "/404", r: "github.com" }])
      && same(run(input.notfound, input.app, { path: "/protocols/alice-jones", beacon: B }).events(), [{ v: 1, h: "wtf", e: "not_found_404", p: "/404" }]);   // Codex F1 probe
    const redact = [["/protocols/no-such-protocol/extra", "/404"], ["/protocols/alice%40example.org", "/404"], ["/protocols/reset-token", "/404"],
      ["/users/john/secret", "/404"], ["/briefs/etherfi-op-0x244e/", "/404"], ["/a@b/" + "x".repeat(200), "/404"], ["/protocols/Aave", "/404"]];
    res.b_not_found_path_sanitised = redact.every(([path, want]) => { const e = run(input.notfound, input.app, { path, beacon: B }).events(); return same(e, [{ v: 1, h: "wtf", e: "not_found_404", p: want }]); });
    const ref = (r) => run(input.index, input.app, { path: "/", referrer: r, beacon: B }).events()[0];
    res.b_c1_referrers_redacted = ["https://192.0.2.44/", "https://10.0.0.1:8080/x", "https://[::1]/", "https://localhost/", "https://box.local/",
      "https://printer.lan/", "https://192-0-2-44.nip.io/", "https://c0a8002c.sslip.io/", "https://2130706433/", "https://0x7f000001/", "http://intranet/",
      "https://box.corp/x", "https://box.intranet/x"]
      .every((r) => !("r" in ref(r))) && ref("https://news.ycombinator.com/item?id=1").r === "news.ycombinator.com";
    const utm = (q) => run(input.index, input.app, { path: "/", search: q, beacon: B }).events()[0];
    res.b_c1_utm_redacted = ["?utm_source=192.0.2.44", "?utm_source=alice.bob", "?utm_source=user-123456", "?utm_source=reset-token", "?utm_source=1abc",
      "?utm_source=" + "x".repeat(25), "?utm_source=alice%40example.org"].every((q) => !("u" in utm(q))) && utm("?utm_source=Twitter").u === "twitter";
    // a slug is taken only from a real page: the path must equal the page's <link rel="canonical"> (Phase C.2)
    const canon = "https://pacta.wtf/protocols/" + input.protocolSlug + "/";
    const pageFor = (url) => JSON.parse(JSON.stringify(input.protocol).split(canon).join(url));
    const pages = (input.protocolSlugs || []).map((sl) => run(pageFor("https://pacta.wtf/protocols/" + sl + "/"), input.app, { path: "/protocols/" + sl + "/", beacon: B }).events()[0]);
    res.b_c1_all_protocol_slugs_kept = pages.length === input.expectProtocols && pages.length === input.protocolSlugs.length && pages.every((e, i) => e.p === "/protocols/" + input.protocolSlugs[i] + "/" && e.t === input.protocolSlugs[i]);
    const mismatch = run(input.protocol, input.app, { path: "/protocols/alice-jones/", beacon: B }).events()[0];
    const brief = run(pageFor("https://pacta.wtf/briefs/etherfi-op-0x244e/"), input.app, { path: "/briefs/etherfi-op-0x244e/", beacon: B }).events()[0];
    res.b_c2_slug_only_from_canonical = same(mismatch, { v: 1, h: "wtf", e: "page_load", p: "/other" }) && same(brief, { v: 1, h: "wtf", e: "page_load", p: "/briefs/etherfi-op-0x244e/" })
      && same(run(input.protocol, input.app, { path: "/protocols/" + input.protocolSlug + "/index.html", beacon: B }).events()[0].p, "/protocols/" + input.protocolSlug + "/");
    const views = [["/request", "/request/"], ["/protocols", "/protocols/"], ["/llms", "/llms/"], ["/llms/index.html", "/llms/"], ["/llms/x", "/other"], ["/briefs/etherfi-op-0x244e/", "/other"],
      ["/protocols/aave-v3-gho/", "/other"], ["/demos/swapio-x402/", "/demos/swapio-x402/"], ["/demos/x", "/other"], ["/reset/alice%40example.org/x", "/other"]];   // index page: canonical is "/"
    res.b_c1_page_paths = views.every(([path, want]) => run(input.index, input.app, { path, beacon: B }).events()[0].p === want);
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
  click(p.document.querySelectorAll("button[data-copy-term]").find(b => /\/mcp$/.test((b.closest(".term").querySelector("pre") || { textContent: "" }).textContent)));
  p.window.scrollY = 3500; (p.winListeners.scroll || []).forEach(fn => fn({}));
  p.window.pactaBeacon("live_checker_submit", "ethereum:0x" + "1".repeat(40));
  res.b_dnt_sends_nothing = p.beacons.length === 0 && sent.length === 0 && typeof p.window.pactaBeacon === "function";
  p = run(input.index, input.app, { path: "/", beacon: B, protocol: "http:", fetch: rec });
  res.b_non_https_sends_nothing = p.beacons.length === 0 && sent.length === 0;
  // no sendBeacon: fetch keepalive no-cors with the same string body
  p = run(input.index, input.app, { path: "/", beacon: B, nav: { sendBeacon: undefined }, fetch: rec });
  await flush();
  res.b_fetch_fallback = sent.length === 1 && sent[0][0] === BEACON && sent[0][1].method === "POST" && sent[0][1].keepalive === true
    && sent[0][1].mode === "no-cors" && same(JSON.parse(sent[0][1].body), { v: 1, h: "wtf", e: "page_load", p: "/" });
  // no cookies, no storage: the beacon run never touches document.cookie or localStorage
  let touched = false;
  const trap = { get: () => { touched = true; return ""; }, set: () => { touched = true; } };
  const t0 = run(input.index, null, { path: "/", beacon: B });   // b.js alone
  Object.defineProperty(t0.document, "cookie", trap);
  click(t0.document.querySelectorAll("button[data-copy], button[data-copy-term]")[0]);
  res.b_no_cookie_access = !touched && t0.events().length >= 1;
  // v5.0+: first-class routes (all live site HTML routes), allowlisted campaign tags (m, c), production-only serving host gate (h), and nothing once 404 rescued or on staging
  const ev0 = (o) => run(input.index, null, Object.assign({ path: "/", beacon: B }, o)).events()[0];
  res.b_v5_routes = [["/scorecards/", "/scorecards/"], ["/curators/", "/curators/"], ["/radar", "/radar/"], ["/bounties/", "/bounties/"], ["/leaderboard/", "/leaderboard/"],
    ["/methodology/", "/methodology/"], ["/scan/", "/scan/"], ["/seal/index.html", "/seal/"], ["/webhook/", "/webhook/"], ["/miniapp/", "/miniapp/"],
    ["/pricing/", "/pricing/"], ["/about/", "/about/"], ["/for-protocols/", "/for-protocols/"], ["/integrations/", "/integrations/"],
    ["/integrations/vault-factories/", "/integrations/vault-factories/"], ["/mcp/", "/mcp/"], ["/demos/", "/demos/"],
    ["/demos/swapio-x402/", "/demos/swapio-x402/"], ["/privacy/", "/privacy/"], ["/terms/", "/terms/"],
    ["/scan/x", "/other"], ["/demos/x", "/other"], ["/evil/", "/other"]].every(([path, want]) => ev0({ path }).p === want);
  res.b_v5_campaign_fields = same(ev0({ search: "?utm_source=x&utm_medium=paid&utm_campaign=Launch_Q4" }), { v: 1, e: "page_load", p: "/", u: "x", m: "paid", c: "launch_q4", h: "wtf" })
    && same(ev0({ path: "/scan/", search: "?utm_source=hypelab&utm_medium=cpc&utm_campaign=hl1_explorers_scanseal" }),
            { v: 1, e: "page_load", p: "/scan/", u: "hypelab", m: "cpc", c: "hl1_explorers_scanseal", h: "wtf" })
    && ev0({ search: "?utm_medium=paid_search" }).m === "paid_search" && ev0({ search: "?utm_medium=Organic" }).m === "organic"
    && ["email", "paid%20x", "paid-search", "", "paidx"].every((m) => !("m" in ev0({ search: "?utm_medium=" + m })))
    && ["0xdeadbeefcafe", "deadbeefcafe12", "user-123456", "reset_token", "x".repeat(33), "launch%20q4", "a.b", "mail_drop", "12345"]
      .every((c) => !("c" in ev0({ search: "?utm_campaign=" + c })));
  res.b_v5_host = ev0({ hostname: "pacta.fractalneurons.com" }).h === "com" && ev0({ hostname: "pacta.fractalneurons.com", referrer: "https://pacta.fractalneurons.com/" }).r === "self"
    && ev0({}).h === "wtf" && ev0({ hostname: "pacta-fractalneurons.pages.dev" }).h === "wtf"
    && run(input.index, null, { path: "/website-test/scan/", hostname: "pacta.dri.network", beacon: B }).beacons.length === 0
    && run(input.index, null, { path: "/", hostname: "localhost", beacon: B }).beacons.length === 0
    && run(input.index, null, { path: "/", hostname: "127.0.0.1", beacon: B }).beacons.length === 0;
  res.b_v5_rescued_sends_nothing = run(input.index, null, { path: "/", beacon: B, win: { pactaRescued: 1 } }).beacons.length === 0;
}
// (o) 404.html stripped-"?" rescue (docs/404-rescue.js): a known route + a stripped query goes back to /<route>/?<query>; nothing else moves
function rescueScenario() {
  if (!input.rescue) { res.r_error = "no rescue source"; return; }
  const go = (pathname, search, hash) => {
    const w = {}; let to = null;
    const L = { pathname, search: search || "", hash: hash || "", replace: (u) => { to = u; } };
    vm.runInNewContext(input.rescue, { window: w, location: L });
    return [to, w.pactaRescued === 1];
  };
  const ok = [["/scorecards/utm_source=x&utm_medium=paid&utm_campaign=d2", "", "", "/scorecards/?utm_source=x&utm_medium=paid&utm_campaign=d2"],
    ["/website-test/request/tier=seal-99", "", "", "/website-test/request/?tier=seal-99"],
    ["/public/web/option-b-v2/seal/tier=seal-99", "", "", "/public/web/option-b-v2/seal/?tier=seal-99"], ["/protocols/aave-v3-gho/ref=x", "", "", "/protocols/aave-v3-gho/?ref=x"],
    ["/scan/utm_campaign=launch", "?b=1", "#checkout", "/scan/?utm_campaign=launch&b=1#checkout"], ["/seal/tier=seal-99", "", "", "/seal/?tier=seal-99"],
    ["/webhook/utm_source=x", "", "", "/webhook/?utm_source=x"], ["/curators/utm_source=x", "", "", "/curators/?utm_source=x"], ["/methodology/ref=hn", "", "", "/methodology/?ref=hn"],
    ["/leaderboard/utm_source=x", "", "", "/leaderboard/?utm_source=x"], ["/protocols/utm_source=x", "", "", "/protocols/?utm_source=x"]];
  res.r_rescues_known_routes = ok.every(([p_, s_, h_, want]) => { const [to, flag] = go(p_, s_, h_); return to === want && flag; });
  const no = ["/scorecards/foo=1", "/evil/utm_source=x", "/scorecards/utm_source=", "//evil.example/scorecards/utm_source=x", "/scorecards/",
    "/protocols/Aave/utm_source=x", "/pricing/utm_source=x", "/scorecards/x/utm_source=y", "/website-test/evil/utm_source=x", "/public/web/other/scan/utm_source=x", "/scorecardsutm_source=x"];
  res.r_leaves_everything_else = no.every((p_) => { const [to, flag] = go(p_); return to === null && !flag; });
}
// (p) Option B self-serve checkout (#checkout): closed SKU enum, exact EIP-681 transfer links, validation before any request, the
//     orders/verify POST body, a text-only result, error paths and the browser-wallet path (chain switch, ERC-20 transfer only)
// (j) live timelock re-check: brief pages and #radar fetch the free /v1/briefs/live-timelocks once on load and update the
// state badges with textContent + class only; failures and malformed payloads keep the static block-pinned state.
async function liveTimelockScenario() {
  if (!input.timelockBrief) { res.live_error = "no timelock brief page"; return; }
  const LIVE = "https://pacta.fractalneurons.com/v1/briefs/live-timelocks?caller_agent=pacta-wtf-radar&requester_role=individual_user&caller_purpose=governance_monitoring";
  const opsOf = (doc) => (doc.querySelector("#post-eta-status [data-ops]").getAttribute("data-ops") || "").split(/\s+/).filter(Boolean);
  const op = (opId, live, block = 26420000) => ({ protocol: "Ethena", opId, live, block: { number: block, hash: "0x" + "ab".repeat(32), timestamp: 1794700000 } });
  const runWith = async (tree, path, reply) => {
    const calls = [];
    const fetchMock = (url, init) => {
      calls.push({ url: String(url), init });
      if (reply instanceof Error) return Promise.reject(reply);
      return Promise.resolve({ status: reply.status, json: () => (reply.bad ? Promise.reject(new Error("bad json")) : Promise.resolve(reply.body)) });
    };
    const p = run(tree, input.app, { path, fetch: fetchMock });
    for (let i = 0; i < 6; i++) await flush();
    return { d: p.document, calls };
  };
  const badge = (d) => d.querySelector("#post-eta-status [data-ops]");
  // static state before any network: READY, never EXECUTED
  let x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", new Error("offline"));
  const ids = opsOf(x.d);
  res.live_static_ready = ids.length === 2 && badge(x.d).textContent === "READY · EXECUTABLE NOW" && badge(x.d).classList.contains("ready")
    && x.calls.length === 1 && x.calls[0].url === LIVE && x.d.querySelector("[data-live-line]").textContent === "";
  // live: both executed -> EXECUTED, banner flips, clause says superseded, latest block named
  x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", { status: 200, body: { operations: ids.map((i) => op(i, { status: "done", isOperationDone: true, isOperationPending: false })) } });
  const ban = x.d.getElementById("post-eta-status");
  res.live_flips_executed = badge(x.d).textContent === "EXECUTED" && badge(x.d).classList.contains("executed") && !badge(x.d).classList.contains("ready")
    && ban.classList.contains("executed") && /live re-check at block #26,420,000: EXECUTED/.test(ban.querySelector(".ps-clause").textContent)
    && /#26,420,000/.test(x.d.querySelector("[data-live-line]").textContent);
  // live: one ready, one done -> MIXED; still ready -> READY (no change of meaning)
  x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", { status: 200, body: { operations: [op(ids[0], { status: "ready", isOperationPending: true, isOperationDone: false }), op(ids[1], { status: "done", isOperationDone: true })] } });
  res.live_mixed = badge(x.d).textContent === "MIXED" && badge(x.d).classList.contains("mixed");
  x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", { status: 200, body: { operations: ids.map((i) => op(i, { status: "ready", isOperationPending: true, isOperationDone: false })) } });
  res.live_ready_kept = badge(x.d).textContent === "READY · EXECUTABLE NOW" && badge(x.d).getAttribute("data-live") === "1";
  // failures keep the static state: HTTP 502, malformed JSON, missing / partial operations, markup in the payload stays text
  let keep = true;
  for (const reply of [{ status: 502, body: {} }, { status: 200, bad: true }, { status: 200, body: { operations: "nope" } },
    { status: 200, body: { operations: [op(ids[0], { status: "done", isOperationDone: true })] } },
    { status: 200, body: { operations: ids.map((i) => op(i, { status: "<img src=x onerror=alert(1)>" })) } }]) {
    x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", reply);
    keep = keep && badge(x.d).textContent === "READY · EXECUTABLE NOW" && !x.d.querySelectorAll("img").some((i) => i.getAttribute("onerror") !== null);
  }
  res.live_failures_keep_static = keep;
  // homepage #radar: the Ethena row badge updates; pages without data-live-timelocks never fetch
  x = await runWith(input.index, "/", { status: 200, body: { operations: ids.map((i) => op(i, { status: "done", isOperationDone: true })) } });
  const row = x.d.querySelectorAll("#radar [data-ops]").find((b) => b.getAttribute("data-ops") === ids.join(" "));
  res.live_radar_row = !!row && row.textContent === "EXECUTED" && x.calls.filter((c) => /live-timelocks/.test(c.url)).length === 1
    && x.calls.filter((c) => /live-timelocks/.test(c.url))[0].url === LIVE;
  x = await runWith(input.request, "/request/", { status: 200, body: { operations: [] } });
  res.live_no_fetch_elsewhere = x.calls.length === 0;
}
// (k2) v4.2 staging: a page built with --base-path records it on <html data-base-path>; runtime site links follow the mount, and a
// malformed value is ignored (the production URL stays)
async function basePathScenario() {
  const withBase = (v) => { const t = JSON.parse(JSON.stringify(input.index)); t[1]["data-base-path"] = v; return t; };
  const body = { ...PF_EXAMPLE, catalogMatch: { slug: "stader-labs-ethx", name: "Stader Labs (ETHx)", url: "https://pacta.wtf/protocols/stader-labs-ethx/",
    classification: "parameter_delta", pinnedBlock: 26403676 } };
  const fetchMock = (url) => /\/v1\/check\/preflight/.test(String(url)) ? Promise.resolve({ status: 200, json: () => Promise.resolve(body) })
    : Promise.reject(new Error("site data not needed here"));
  const link = async (tree, path) => {
    const p = run(tree, input.app, { path, fetch: fetchMock });
    const f = p.document.getElementById("pf-form");
    f.querySelector('input[name="address"]').value = PF_EXAMPLE.address; f.dispatchEvent(new Event_("submit"));
    for (let i = 0; i < 4; i++) await flush();
    const a = p.document.getElementById("pf-out").querySelectorAll("a").find((x) => x.textContent === "Full record");
    return a ? a.getAttribute("href") : null;
  };
  res.v42_base_path_catalog_link = (await link(withBase("/website-test"), "/website-test/")) === "/website-test/protocols/stader-labs-ethx/";
  res.v42_base_path_rejects_bad_values = (await link(withBase("javascript:alert(1)//"), "/website-test/")) === "https://pacta.wtf/protocols/stader-labs-ethx/"
    && (await link(input.index, "/")) === "https://pacta.wtf/protocols/stader-labs-ethx/";
  // v4.2.1 (D1): a standalone "." or ".." segment would leave the mount, so it is ignored; normal dotted names still work
  let dots = true;
  for (const v of ["/..", "/.", "/website-test/../../evil", "/website-test/."]) {
    dots = dots && (await link(withBase(v), "/website-test/")) === "https://pacta.wtf/protocols/stader-labs-ethx/";
  }
  res.v421_base_path_rejects_dot_segments = dots;
  res.v421_base_path_allows_dotted_names = (await link(withBase("/release.v4"), "/release.v4/")) === "/release.v4/protocols/stader-labs-ethx/";
}
// (j2) T1 late-payload race (v4.1): once the 9 s fallback has shown the pinned snapshot, a live response that resolves afterwards
// (the fetch itself, or a slow r.json() body) never changes a badge or the status line, and the guard aborts the request.
async function lateLivePayloadScenario() {
  const scen = async (lateBody) => {
    const timers = [], signals = [];
    let releaseFetch = null, releaseJson = null;
    const fetchMock = (url, init) => {
      if (!/live-timelocks/.test(String(url))) return Promise.reject(new Error("site data not needed here"));
      signals.push(init && init.signal);
      const body = () => new Promise((r) => { releaseJson = r; });
      if (lateBody) return Promise.resolve({ status: 200, json: body });   // headers arrive, the body decodes late
      return new Promise((r) => { releaseFetch = () => r({ status: 200, json: () => Promise.resolve(releaseFetch.payload) }); });
    };
    const p = run(input.index, input.app, { path: "/", fetch: fetchMock, setTimeout: (fn, ms) => { timers.push({ fn, ms }); return timers.length; } });
    for (let i = 0; i < 4; i++) await flush();
    const d = p.document, badges = () => d.querySelectorAll("#radar [data-ops]");
    const snap = () => badges().map((b) => b.getAttribute("data-opstate") + "|" + b.textContent + "|" + (b.getAttribute("data-live") || "")).join(";")
      + "#" + d.querySelector("[data-live-status-text]").textContent + "#" + d.querySelector("[data-radar-counts]").textContent;
    const pendingBefore = !!d.querySelector("[data-live-pending]");
    const guard = timers.find((t) => t.ms === 9000);
    if (!guard) return { ok: false, why: "no 9000 ms guard" };
    guard.fn();
    const afterGuard = snap();
    const fallbackShown = /Live check unavailable: showing the pinned snapshot/.test(afterGuard) && !d.querySelector("[data-live-pending]");
    const payload = { operations: badges().flatMap((b) => (b.getAttribute("data-ops") || "").split(/\s+/).filter(Boolean))
      .map((id) => ({ opId: id, live: { status: "pending", isOperationPending: true, isOperationDone: false }, block: { number: 26999999 } })) };
    if (lateBody) releaseJson(payload); else { releaseFetch.payload = payload; releaseFetch(); }
    for (let i = 0; i < 6; i++) await flush();
    return { ok: pendingBefore && fallbackShown && snap() === afterGuard && !!signals[0] && signals[0].aborted === true
      && !badges().some((b) => b.getAttribute("data-live") === "1"), afterGuard, after: snap() };
  };
  const a = await scen(false), b = await scen(true);
  res.t1_late_payload_after_fallback_ignored = a.ok === true;
  res.t1_late_json_body_after_fallback_ignored = b.ok === true;
}
// /protocols/ (visitor review P1): Status x Chain x search combine (intersection); "Clear all" resets all three; 0 matches renders a
// one-click recovery prompt (textContent + data-precover buttons, no inline handlers); rows only toggle the hidden attribute.
function protocolFilterScenario() {
  if (!input.protocolsIndex) return;
  const x = run(input.protocolsIndex, input.app, { path: "/protocols/" }), d = x.document;
  const rows = d.querySelectorAll("#proto-table tbody tr"), shown = () => rows.filter((r) => !r.hidden);
  const count = () => d.getElementById("proto-count").textContent, q = d.getElementById("proto-q");
  const btn = (kind, k) => d.querySelectorAll(`[data-pfilter-${kind}]`).find((b) => b.getAttribute(`data-pfilter-${kind}`) === k);
  const press = (b) => { const ev = new Event_("click"); ev.target = b; b.dispatchEvent(ev); };
  const click = (kind, k) => press(btn(kind, k));
  const type = (v) => { q.value = v; const ev = new Event_("input"); ev.target = q; q.dispatchEvent(ev); };
  const pressed = (kind) => d.querySelectorAll(`[data-pfilter-${kind}][aria-pressed="true"]`).map((b) => b.getAttribute(`data-pfilter-${kind}`));
  const tierIs = (t) => (r) => r.getAttribute("data-ptier") === t, chainHas = (c) => (r) => r.getAttribute("data-pchains").split(" ").includes(c);
  const n = rows.length, want = (pred) => rows.filter(pred).length, empty = d.getElementById("proto-empty"), clear = d.getElementById("proto-clear");
  res.pfilter_initial_all = n === input.expectProtocols && shown().length === n && count() === n + " of " + n + " protocols shown" && empty.hidden && clear.hidden;
  let ok = true;
  // v4: one vocabulary (M3) and the scorecard counts (M4): Docs differ / Protective / Aligned / Observed, labels "(n)"
  for (const [kind, k, pred] of [["status", "aligned", tierIs("aligned")], ["status", "delta", tierIs("delta")], ["status", "protective", tierIs("protective")],
    ["status", "observed", tierIs("observed")],
    ["chain", "ethereum", chainHas("ethereum")], ["chain", "base", chainHas("base")]]) {
    click("status", "all"); click("chain", "all"); click(kind, k);
    const label = (btn(kind, k).querySelector(".num") || { textContent: "" }).textContent;
    ok = ok && shown().length === want(pred) && shown().every(pred) && "(" + want(pred) + ")" === label && pressed(kind).join() === k
      && count() === want(pred) + " of " + n + " protocols shown";
  }
  res.pfilter_pills_exact = ok;
  // independent groups intersect: Status Parameter Delta x Chain Base = rows that are both
  click("status", "delta"); click("chain", "base");
  const both = (r) => tierIs("delta")(r) && chainHas("base")(r);
  res.pfilter_status_x_chain = pressed("status").join() === "delta" && pressed("chain").join() === "base" && shown().length === want(both)
    && shown().every(both) && want(both) < want(tierIs("delta"))
    && d.getElementById("proto-active").textContent.includes("Docs vs chain: Docs differ") && d.getElementById("proto-active").textContent.includes("Chain: Base") && !clear.hidden;
  click("status", "all"); click("chain", "all"); type("ethena");
  res.pfilter_text_search = shown().length >= 1 && shown().every((r) => (r.getAttribute("data-psearch") || "").includes("ethena")) && shown().length < n;
  // 0 matches: recovery prompt names the active filters and offers one-click fixes
  click("chain", "base"); type("stader");
  const recover = (k) => empty.querySelectorAll("[data-precover]").find((b) => b.getAttribute("data-precover") === k);
  res.pfilter_empty_prompt = shown().length === 0 && !empty.hidden && empty.textContent.includes("No Base protocols match “stader”")
    && !!recover("chain") && !!recover("search") && !recover("status") && count() === "0 of " + n + " protocols shown";
  press(recover("chain"));
  res.pfilter_recover_chain = shown().length >= 1 && shown().every((r) => (r.getAttribute("data-psearch") || "").includes("stader")) && pressed("chain").join() === "all"
    && empty.hidden && q.value === "stader";
  type("<img src=x onerror=alert(1)>");
  res.pfilter_inert = shown().length === 0 && d.querySelectorAll("img").every((i) => i.getAttribute("onerror") === null) && !empty.hidden
    && empty.querySelectorAll("img").length === 0;
  click("status", "aligned"); click("chain", "ethereum"); type("aave");
  press(clear);
  res.pfilter_clear_all = shown().length === n && q.value === "" && pressed("status").join() === "all" && pressed("chain").join() === "all" && clear.hidden
    && d.getElementById("proto-active").textContent === "";
  res.pfilter_reset = shown().length === n;
  // curator baskets: each basket shows exactly its tagged rows, combines with Chain, and Clear all resets it
  const inB = (k) => (r) => (r.getAttribute("data-pbaskets") || "").split(" ").includes(k);
  let bok = true;
  for (const k of ["stable_rwa", "eth_lst_lrt", "lending_vaults", "base"]) {
    click("basket", k);
    if (!(shown().length === want(inB(k)) && shown().length > 0 && pressed("basket").join() === k)) bok = false;
  }
  click("basket", "stable_rwa"); click("chain", "base");
  const comb = shown().length === want((r) => inB("stable_rwa")(r) && chainHas("base")(r)) && /Basket: Stablecoins & RWA/.test(d.getElementById("proto-active").textContent);
  press(clear);
  res.pp2_baskets_protocols = bok && comb && shown().length === n && pressed("basket").join() === "all";
}

// Visitor review P1 / P2 (homepage): live check first (hero button -> one preflight call), confidence framing + catalogMatch next to the
// score, the pinned-catalog fallback, pinned-snapshot ages, and the inspector "What differs" (JS) == tools/control_diff.py for every
// flagged record. Everything is rendered with textContent; a catalogMatch URL that is not a pacta.wtf record page is never linked.
async function visitorScenario() {
  const calls = [];
  let reply = { status: 200, body: PF_EXAMPLE };
  const fetchMock = (url) => {
    const u = String(url);
    if (/api\/v1\/scorecards\.json/.test(u) && input.scorecardsJson) return Promise.resolve({ status: 200, json: () => Promise.resolve(input.scorecardsJson) });
    if (/api\/v1\/index\.json/.test(u) && input.indexJson) return Promise.resolve({ status: 200, json: () => Promise.resolve(input.indexJson) });
    if (!/\/v1\/check\/preflight/.test(u)) return Promise.reject(new Error("not needed"));
    calls.push(u); const r = reply; return Promise.resolve({ status: r.status, json: () => Promise.resolve(r.body) });
  };
  const p = run(input.index, input.app, { path: "/", fetch: fetchMock });
  const d = p.document, out = d.getElementById("pf-out");
  await flush(); await flush(); await flush();
  // Edge v3 hero: three receipts; a click renders the pinned receipt instantly and runs the live check of the same contract
  const rec = d.querySelectorAll("[data-receipt]"), go = rec[0], pc = d.querySelector("[data-proof-card]");   // V6 proof card
  reply = { status: 200, body: { ...PF_EXAMPLE, verdict: "UNCLASSIFIED_CONTRACT_CONTROLLER", riskScore: 60, source: "live_rpc",
    assessment: { coverage: "indexed_verified", confidence: "medium", method: "Live bytecode + storage heuristic", limits: ["riskScore is a heuristic."] },
    catalogMatch: { slug: "stader-labs-ethx", name: "Stader Labs (ETHx)", url: "https://pacta.wtf/protocols/stader-labs-ethx/", classification: "parameter_delta",
      pinnedBlock: 26403676, whatDiffers: { changed: [{ parameter: "Safe threshold", observed: "3-of-6", documented: "3-of-5" }],
        matched: [{ parameter: "Timelock delay", value: "7 d" }] } } } };
  go.dispatchEvent(new Event_("click"));
  const pcv = (s) => (pc.querySelector(s) || { textContent: "" }).textContent;
  const instant = !!pc && pcv("[data-pc-name]") === "Stader ETHx" && pcv("[data-pc-docs]") === "Manager Safe is 3-of-5" && pcv("[data-pc-chain]") === "Manager Safe is 3-of-6"
    && /^Ethereum #[\d,]+$/.test(pcv("[data-pc-block]")) && pc.querySelector("[data-pc-href]").getAttribute("href") === "protocols/stader-labs-ethx/"
    && go.getAttribute("aria-pressed") === "true";
  await flush(); await flush(); await flush();
  const t = out.textContent, link = out.querySelectorAll("a").find((a) => a.textContent === "Full record");
  res.v_hero_receipts = rec.length === 3 && instant && rec.every((b) => /^0x[0-9a-fA-F]{40}$/.test(b.getAttribute("data-pf-address") || ""))
    && rec.map((b) => b.getAttribute("data-r-name")).join("|") === "Stader ETHx|YO Protocol|Moonwell (Base)";
  res.v_hero_click_fetches = calls.length === 1 && calls[0].includes("address=" + go.getAttribute("data-pf-address"));
  res.v_assessment_next_to_score = t.includes("Heuristic score") && t.includes("60/100") && t.includes("Confidence medium") && t.includes("Indexed & verified record")
    && t.includes("Limits: riskScore is a heuristic.");
  res.v_catalog_match = t.includes("Indexed by Pacta: Stader Labs (ETHx)") && t.includes("Changed: Safe threshold 3-of-6 observed vs 3-of-5 documented")
    && t.includes("Matched: Timelock delay: 7 d") && !!link && link.getAttribute("href") === "https://pacta.wtf/protocols/stader-labs-ethx/";
  reply = { status: 200, body: { ...reply.body, catalogMatch: { ...reply.body.catalogMatch, url: "javascript:alert(1)", name: "<img src=x onerror=alert(1)>" } } };
  go.dispatchEvent(new Event_("click"));
  await flush(); await flush(); await flush();
  res.v_catalog_url_guard = !out.querySelectorAll("a").some((a) => /javascript:/i.test(a.getAttribute("href") || "")) && out.querySelectorAll("img").length === 0;
  reply = { status: 200, body: { schema: "pacta.preflight_catalog_fallback.v1", source: "pinned_catalog_fallback", verdict: null, riskScore: null,
    summary: "Live RPC unavailable; Stader Labs (ETHx) is indexed by Pacta.", assessment: { coverage: "indexed_verified", confidence: "medium", method: "No live read", limits: [] },
    catalogMatch: { slug: "stader-labs-ethx", name: "Stader Labs (ETHx)", url: "https://pacta.wtf/protocols/stader-labs-ethx/", classification: "parameter_delta", pinnedBlock: 26403676 } } };
  go.dispatchEvent(new Event_("click"));
  await flush(); await flush(); await flush();
  res.v_fallback_rendered = out.textContent.includes("Pinned record") && out.textContent.includes("Live RPC unavailable")
    && out.textContent.includes("Indexed by Pacta: Stader Labs (ETHx)") && !/HTTP 200/.test(out.textContent);
  // the hero checker flags a malformed address on its own input (aria-invalid + aria-describedby) and clears it on a valid one
  const pf = d.getElementById("pf-form"), pin = pf.querySelector('input[name="address"]');
  pin.value = "0x123"; pf.dispatchEvent(new Event_("submit")); await flush();
  const bad = pin.getAttribute("aria-invalid") === "true" && pin.getAttribute("aria-describedby") === "pf-addr-error"
    && d.getElementById("pf-addr-error").textContent.length > 0 && d.getElementById("pf-addr-error").hidden === false;
  pin.value = "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b"; pf.dispatchEvent(new Event_("submit")); await flush(); await flush(); await flush();
  res.e3_checker_aria_invalid = bad && pin.getAttribute("aria-invalid") === null && pin.getAttribute("aria-describedby") === "pf-help"
    && d.getElementById("pf-addr-error").hidden === true;
  const ages = d.querySelectorAll("[data-age]");
  res.v_ages = ages.length >= 2 && ages.every((a) => / \(\d+d \d+h \d+m ago\)$| \(\d+h \d+m ago\)$/.test(a.textContent));
  // Edge v3 scorecards (v4.7 W1): 8 static high-signal rows; search / filters hydrate every protocol from /api/v1/scorecards.json
  const cards = (input.scorecardsJson && input.scorecardsJson.protocols) || [];
  const rowsNow = () => d.querySelectorAll("#scorecards tr.sc-row"), visible = () => rowsNow().filter((r) => !r.hidden);
  res.e3_static_preview = rowsNow().length === 8 && d.querySelectorAll("#scorecards tr.sc-drawer").length === 8
    && rowsNow().every((r) => r.querySelector("svg.rosette") && r.querySelector(".grade"));
  // a drawer opens / closes from its row toggle and carries the 5-factor breakdown
  const tog0 = rowsNow()[0].querySelector(".sc-toggle"), dr0 = d.getElementById(tog0.getAttribute("aria-controls"));
  let ev = new Event_("click"); ev.target = tog0; d.querySelector("[data-sc-body]").dispatchEvent(ev);
  const opened = dr0.hidden === false && tog0.getAttribute("aria-expanded") === "true" && dr0.querySelectorAll("[data-factor]").length === 5;
  ev = new Event_("click"); ev.target = tog0; d.querySelector("[data-sc-body]").dispatchEvent(ev);
  res.e3_drawer_toggle = opened && dr0.hidden === true && tog0.getAttribute("aria-expanded") === "false";
  // U4 (v4): a click anywhere in the row (here the "What differs" cell) toggles it too; the row carries .open while expanded
  const find0 = rowsNow()[0].querySelector(".sc-find");
  ev = new Event_("click"); ev.target = find0; d.querySelector("[data-sc-body]").dispatchEvent(ev);
  const rowOpen = dr0.hidden === false && rowsNow()[0].classList.contains("open") && tog0.getAttribute("aria-expanded") === "true";
  ev = new Event_("click"); ev.target = find0; d.querySelector("[data-sc-body]").dispatchEvent(ev);
  res.v4_whole_row_toggle = rowOpen && dr0.hidden === true && !rowsNow()[0].classList.contains("open")
    && rowsNow().every((r) => (r.querySelector(".sc-find").textContent || "").length <= 90 && !/…/.test(r.querySelector(".sc-find").textContent));
  d.querySelectorAll("[data-sc-f]").find((b) => b.getAttribute("data-sc-f") === "all").dispatchEvent(new Event_("click"));   // any filter hydrates
  for (let i = 0; i < 4; i++) await flush();
  const all = rowsNow();
  res.e3_hydrated_all = cards.length === all.length && all.length > 8 && !d.querySelector("[data-sc-all]")
    && /^Explore all \d+ protocol scorecards$/.test(d.querySelector("[data-sc-explore]").textContent) && d.querySelector("[data-sc-explore]").getAttribute("href") === "scorecards/"
    && all.every((r) => r.querySelector("svg.rosette") && r.querySelector("svg.rosette").querySelectorAll("path").length === 5
      && /Upgradeability .*Timelock floor .*Signer quorum .*Emergency \/ freeze scope .*Docs-vs-chain parity/.test(r.querySelector("svg.rosette").getAttribute("aria-label") || ""))
    && d.querySelectorAll("#scorecards tr.sc-drawer").length === cards.length;
  const obs = cards.filter((c) => !c.easAttested).map((c) => c.slug);
  res.e3_observed_parity_hollow = obs.length > 0 && obs.every((s) => {
    const r = all.find((x) => x.getAttribute("data-slug") === s); const ps = r ? r.querySelector("svg.rosette").querySelectorAll("path") : [];
    return ps.length === 5 && ps[4].getAttribute("class") === "r-u";
  });
  const pill = (k) => d.querySelectorAll("[data-sc-f]").find((b) => b.getAttribute("data-sc-f") === k);
  pill("delta").dispatchEvent(new Event_("click")); await flush(); await flush();
  const nDelta = cards.filter((c) => c.grade === "delta").length;
  res.e3_filter_deltas = visible().length === nDelta && visible().every((r) => r.getAttribute("data-grade") === "delta") && pill("delta").getAttribute("aria-pressed") === "true";
  // v4: the basket is its own Select and intersects with the Docs-vs-chain filter
  const bsel = d.querySelector("[data-sc-basket]"), basket = (v) => { bsel.value = v; const e = new Event_("change"); e.target = bsel; bsel.dispatchEvent(e); };
  basket("base"); await flush(); await flush();
  const deltaBase = visible().length === cards.filter((c) => c.grade === "delta" && (c.baskets || []).includes("base")).length;
  pill("all").dispatchEvent(new Event_("click")); await flush(); await flush();
  res.e3_filter_basket = deltaBase && visible().length === cards.filter((c) => (c.baskets || []).includes("base")).length && visible().length > 0;
  basket("all"); await flush();
  const q = d.getElementById("sc-q");
  pill("all").dispatchEvent(new Event_("click")); await flush();
  const tg = visible()[0].querySelector(".sc-toggle"); ev = new Event_("click"); ev.target = tg; d.querySelector("[data-sc-body]").dispatchEvent(ev);
  q.value = "zzz-no-such-protocol"; q.dispatchEvent(new Event_("input")); await flush(); await flush();
  const emp = d.querySelector("[data-sc-empty]");
  res.e3_zero_match = visible().length === 0 && emp.hidden === false && d.querySelectorAll("#scorecards tr.sc-drawer").every((x) => x.hidden);
  emp.querySelector("[data-sc-clear]").dispatchEvent(new Event_("click")); await flush();
  res.e3_clear_filters = q.value === "" && visible().length === cards.length && emp.hidden === true && pill("all").getAttribute("aria-pressed") === "true"
    && bsel.value === "all";
  q.value = "usdc"; q.dispatchEvent(new Event_("input")); await flush(); await flush();
  res.e3_search = visible().some((r) => r.getAttribute("data-slug") === "circle-usdc") && visible().length < cards.length;
  const rc = d.querySelector("[data-radar-counts]");
  // M4 (v4): the header counts the rows by state; N5 (v4.3): executed rows are counted by operations, e.g.
  // "1 ready · 1 pending · Executed (2 ops)", so the line never reads as a total
  const OPS = "( \\(\\d+ ops?\\))?", PART = "(\\d+ (ready|pending|mixed|cancelled or unknown)" + OPS + "|Executed \\(\\d+ ops?\\))";
  const parts = rc ? rc.textContent.split(" · ") : [], execRows = d.querySelectorAll('#radar tr[data-radar-row="executed"]').length;
  res.pp2_radar_counts = !!rc && new RegExp("^" + PART + "( · " + PART + ")*$").test(rc.textContent)
    && d.querySelectorAll("#radar tr[data-radar-row]").length === parts.reduce((s, x) => s + (/^Executed/.test(x) ? 0 : parseInt(x, 10)), 0) + execRows
    && (execRows === 0) === !parts.some((x) => /^Executed \(\d+ ops?\)$/.test(x)) && !/operations\)/.test(rc.textContent);
}

// F05 "Verify live on RPC" (behavioural): a mocked JSON-RPC responder for the four public RPCs records every call, so the test asserts
// eth_blockNumber comes first and the read is pinned to that exact hex block; the rendered text carries the decimal live block
// number, the full hex word, the decoded value, the RPC host and the latency in ms. Also D1 (IMMUTABLE_NO_ADMIN headline).
const LIVE_N = 26430123, LIVE_HEX = "0x" + LIVE_N.toString(16);
const RPC_HOST_RE = /^https:\/\/(ethereum-rpc\.publicnode\.com|eth\.drpc\.org|base-rpc\.publicnode\.com|mainnet\.base\.org)$/;
const W_ADDR = "0x000000000000000000000000" + "3333333333333333333333333333333333333333";
const W_UINT = "0x" + "0".repeat(63) + "3";
const ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103";
async function liveRpcScenario() {
  const log = []; let reply = PF_EXAMPLE, rpcFail = false;
  const fetchMock = (url, init) => {
    const u = String(url);
    if (RPC_HOST_RE.test(u)) {
      const q = JSON.parse(init.body); log.push({ url: u, method: q.method, params: q.params });
      if (rpcFail) return Promise.resolve({ status: 200, json: () => Promise.resolve({ jsonrpc: "2.0", id: 1, error: { code: -32000, message: "upstream down" } }) });
      let result = null;
      if (q.method === "eth_blockNumber") result = LIVE_HEX;
      else if (q.method === "eth_getBlockByNumber") result = { number: q.params[0], hash: "0x" + "ab".repeat(32) };
      else if (q.method === "eth_getCode") result = "0x6080604052";
      else if (q.method === "eth_getStorageAt") result = W_ADDR;
      else if (q.method === "eth_call") result = q.params[0].data === "0x8da5cb5b" ? W_ADDR : W_UINT;
      return Promise.resolve({ status: 200, json: () => Promise.resolve({ jsonrpc: "2.0", id: 1, result }) });
    }
    if (/\/v1\/check\/preflight/.test(u)) return Promise.resolve({ status: 200, json: () => Promise.resolve(reply) });
    if (/api\/v1\/index\.json/.test(u) && input.indexJson) return Promise.resolve({ status: 200, json: () => Promise.resolve(input.indexJson) });
    return Promise.reject(new Error("not needed"));
  };
  const p = run(input.index, input.app, { path: "/", fetch: fetchMock });
  const d = p.document, out = d.getElementById("pf-out"), tog = d.querySelector("#scorecards .sc-toggle");
  const panel = d.getElementById(tog.getAttribute("aria-controls"));
  for (let i = 0; i < 4; i++) await flush();
  const clickLive = async (root) => {
    const b = root.querySelector("[data-live-verify-btn]"); if (!b) return null;
    b.dispatchEvent(new Event_("click")); for (let i = 0; i < 10; i++) await flush();
    return root.querySelector("[data-live-verify-out]").textContent;
  };
  const tail = (q) => q.params[q.params.length - 1];
  // (1) scorecard drawer: opening it attaches Verify live on RPC for the protocol's lead record, read at a fresh block
  { const ev = new Event_("click"); ev.target = tog; d.querySelector("[data-sc-body]").dispatchEvent(ev); await flush(); }
  log.length = 0;
  const it = await clickLive(panel);
  res.pp3_inspector_live_rpc = !!it && log.length === 2 && log[0].method === "eth_blockNumber" && ["eth_call", "eth_getStorageAt"].includes(log[1].method)
    && tail(log[1]) === LIVE_HEX && it.includes("Live at block #" + LIVE_N + " (" + LIVE_HEX + ")")
    && ((it.includes("Raw: " + W_UINT) && it.includes("Decoded: uint256 3")) || (it.includes("Raw: " + W_ADDR) && it.includes("= address 0x3333333333333333333333333333333333333333")))
    && /(ethereum-rpc|base-rpc)\.publicnode\.com · \d+ ms$/.test(it) && panel.querySelectorAll(".lv-line").length === 4;
  // (2) pre-flight on a proxy: pinned block hash match + live block, eth_getCode and the EIP-1967 admin slot at that block
  const form = d.getElementById("pf-form");
  const submit = async (body) => {
    reply = body; form.querySelector('select[name="chain"]').value = "base"; form.querySelector('input[name="address"]').value = PF_EXAMPLE.address;
    form.dispatchEvent(new Event_("submit")); for (let i = 0; i < 4; i++) await flush();
  };
  await submit(PF_EXAMPLE);
  log.length = 0;
  const pt = await clickLive(out);
  const m = (k) => log.filter((q) => q.method === k);
  res.pp3_preflight_live_rpc_proxy = !!pt && m("eth_getBlockByNumber").length === 1 && m("eth_getBlockByNumber")[0].params[0] === "0x" + (23800000).toString(16)
    && m("eth_blockNumber").length === 1 && m("eth_getCode").length === 1 && tail(m("eth_getCode")[0]) === LIVE_HEX
    && m("eth_getStorageAt").length === 1 && m("eth_getStorageAt")[0].params[1] === ADMIN_SLOT && tail(m("eth_getStorageAt")[0]) === LIVE_HEX
    && log.indexOf(m("eth_blockNumber")[0]) < log.indexOf(m("eth_getCode")[0]) && log.every((q) => /base/.test(q.url))
    && pt.includes("Pinned block #23800000 hash 0x" + "ab".repeat(32) + " matches the pinned hash")
    && pt.includes("Live at block #" + LIVE_N + " (" + LIVE_HEX + "): eth_getCode 5 bytes") && pt.includes("EIP-1967 admin slot: " + W_ADDR)
    && pt.includes("Decoded: uint256 ") && pt.includes("= address 0x3333333333333333333333333333333333333333")
    && (pt.match(/base-rpc\.publicnode\.com · \d+ ms/g) || []).length === 2;
  // (3) D1 + non-proxy: IMMUTABLE_NO_ADMIN renders the exact headline (heuristic caveat kept); the live read is owner() at the fresh block
  await submit({ ...PF_EXAMPLE, verdict: "IMMUTABLE_NO_ADMIN", riskScore: 0, isProxy: false, implementation: null, hasAdminSlot: false,
    controller: { address: null, kind: "none" }, capabilities: {}, summary: "No admin surface found." });
  const vt = out.querySelector(".pf-verdict"), vb = out.querySelector("[data-pf-badge]");
  // V7: the immutable result is neutral (never the amber warning badge); the score still says it rates this one address
  res.pp3_immutable_headline = !!vt && vt.textContent === "No standard upgrade or admin authority detected" && !!vb && vb.getAttribute("data-variant") === "neutral"
    && out.textContent.includes("0/100") && !!out.querySelector("[data-pf-scope]") && !out.textContent.includes("cannot be changed");
  log.length = 0;
  const ot = await clickLive(out);
  res.pp3_preflight_live_rpc_owner = !!ot && m("eth_call").length === 1 && m("eth_call")[0].params[0].data === "0x8da5cb5b"
    && m("eth_call")[0].params[0].to === PF_EXAMPLE.address && tail(m("eth_call")[0]) === LIVE_HEX && m("eth_getStorageAt").length === 0
    && ot.includes("owner(): " + W_ADDR) && ot.includes("= address 0x3333333333333333333333333333333333333333") && ot.includes("#" + LIVE_N) && /\d+ ms$/.test(ot);
  // (4) both public RPCs fail: each endpoint is tried once and the failure is reported (no throw, no stale value)
  rpcFail = true; log.length = 0;
  const ft = await clickLive(panel);
  res.pp3_live_rpc_failure = !!ft && ft.startsWith("Live RPC check failed (upstream down)") && log.length === 2 && log[0].url !== log[1].url
    && log.every((q) => q.method === "eth_blockNumber");
}

// v4.3 N1: a "Try:" example fills #pf-form (chain + address, previous error cleared) and runs ONE live check whose verdict card renders
// in #pf-out right under the form; the proof card follows the example. Also: one init that throws (simulated) never leaves the
// examples or the checker unbound (every init starts on its own), and the error is still reported.
async function tryExampleScenario() {
  const calls = [];
  const fetchMock = (url) => {
    const u = String(url);
    if (!/\/v1\/check\/preflight/.test(u)) return Promise.reject(new Error("not needed"));
    calls.push(u); return Promise.resolve({ status: 200, json: () => Promise.resolve(PF_EXAMPLE) });
  };
  const flow = async (loc) => {
    const p = run(input.index, input.app, Object.assign({ path: "/", fetch: fetchMock }, loc));
    const d = p.document, form = d.getElementById("pf-form"), out = d.getElementById("pf-out");
    const sel = form.querySelector('select[name="chain"]'), addr = form.querySelector('input[name="address"]'), err = d.getElementById("pf-addr-error");
    const chips = d.querySelectorAll("[data-receipt]"), yo = chips.find((b) => b.getAttribute("data-r-name") === "YO Protocol");
    const stader = chips.find((b) => b.getAttribute("data-r-name") === "Stader ETHx");
    calls.length = 0;
    addr.value = "0x123"; form.dispatchEvent(new Event_("submit")); await flush();
    const errShown = addr.getAttribute("aria-invalid") === "true" && err.hidden === false && calls.length === 0;
    yo.dispatchEvent(new Event_("click")); await flush(); await flush(); await flush();
    const box = form.parentNode, kids = box.children;
    const yoOk = errShown && sel.value === "base" && addr.value === yo.getAttribute("data-pf-address") && addr.getAttribute("aria-invalid") === null
      && err.hidden === true && err.textContent === "" && calls.length === 1
      && calls[0].includes("chain=base&address=" + yo.getAttribute("data-pf-address"))
      && !!out.querySelector("[data-pf-result]") && out.textContent.includes("Heuristic score") && out.textContent.includes("MULTISIG_NO_TIMELOCK")
      && out.parentNode === box && kids.indexOf(form) >= 0 && kids.indexOf(form) < kids.indexOf(out)
      && d.querySelector("[data-pc-name]").textContent === "YO Protocol" && yo.getAttribute("aria-pressed") === "true";
    stader.dispatchEvent(new Event_("click")); await flush(); await flush(); await flush();
    const staderOk = sel.value === "ethereum" && addr.value === stader.getAttribute("data-pf-address") && calls.length === 2
      && calls[1].includes("chain=ethereum&address=" + stader.getAttribute("data-pf-address")) && !!out.querySelector("[data-pf-result]")
      && d.querySelector("[data-pc-name]").textContent === "Stader ETHx" && stader.getAttribute("aria-pressed") === "true"
      && yo.getAttribute("aria-pressed") === "false";
    return { ok: yoOk && staderOk, initErrors: p.initErrors };
  };
  const a = await flow({});
  res.v43_n1_try_fills_and_runs = a.ok && a.initErrors.length === 0;
  const b = await flow({ breakTheme: true });
  res.v43_init_isolation = b.ok && b.initErrors.length === 1 && /simulated early init failure/.test(b.initErrors[0]);
}
// v4.7 W1-W5: severity-ordered 8-row preview; dual-audience tabs (arrow keys, Home / End, a link opening a tab); the Ctrl/Cmd+K and
// "/" command dialog over lookup.json + scorecards.json; the hero checker resolving a protocol / token name; the labelled theme button
async function v47Scenario() {
  const lkMock = (url) => /api\/v1\/lookup\.json$/.test(String(url)) ? Promise.resolve({ status: 200, json: () => Promise.resolve(input.lookupJson) })
    : /api\/v1\/scorecards\.json$/.test(String(url)) ? Promise.resolve({ status: 200, json: () => Promise.resolve(input.scorecardsJson) })
    : Promise.reject(new Error("not needed"));
  const p = run(input.index, input.app, { path: "/", fetch: lkMock });
  const d = p.document, key = (target, k, mods) => { const ev = Object.assign(new Event_("keydown"), { key: k, target }, mods || {}); target.dispatchEvent(ev); return ev; };
  const grades = d.querySelectorAll("#scorecards tr.sc-row").map((r) => r.getAttribute("data-grade"));
  const rank = { delta: 0, protective: 1, aligned: 2, observed: 3 };
  res.v47_w1_preview = grades.length === 8 && grades[0] === "delta" && grades.every((g, i) => i === 0 || rank[grades[i - 1]] <= rank[g])
    && /queued operations on Ethereum/.test((d.querySelector("[data-tl-strip]") || { textContent: "" }).textContent)
    && (d.querySelector("[data-tl-strip] a") || { getAttribute: () => "" }).getAttribute("href") === "#radar"
    && /^Pinned blocks: Ethereum #[\d,]+ · Base #[\d,]+ · \d+ Base EAS batches$/.test((d.querySelector("[data-fresh]") || { textContent: "" }).textContent);
  // W2: tabs
  const tRisk = d.getElementById("hiw-t-risk"), tAg = d.getElementById("hiw-t-agents"), pRisk = d.getElementById("hiw-p-risk"), pAg = d.getElementById("hiw-p-agents");
  const sel = () => [tRisk.getAttribute("aria-selected"), tAg.getAttribute("aria-selected"), pRisk.hasAttribute("data-inactive"), pAg.hasAttribute("data-inactive")].join();
  // v4.7.1 V47-01: the inactive panel is inert and aria-hidden from the start, and follows every switch
  const hid = (pn) => pn.hasAttribute("inert") && pn.getAttribute("aria-hidden") === "true";
  const a11y0 = !hid(pRisk) && hid(pAg);
  const s0 = sel(); key(tRisk, "ArrowRight"); const s1 = sel(); const a11y1 = hid(pRisk) && !hid(pAg); key(tAg, "Home"); const s2 = sel(); key(tRisk, "End"); const s3 = sel(); key(tAg, "ArrowLeft"); const s4 = sel();
  const link = d.querySelector('[data-tab-open="hiw-t-agents"]'); link.dispatchEvent(new Event_("click")); const s5 = sel();
  res.v471_tabs_inert = a11y0 && a11y1 && d.querySelector("#how-it-works [data-tabs-stable]") !== null;
  res.v47_w2_tabs = s0 === "true,false,false,true" && s1 === "false,true,true,false" && s2 === s0 && s3 === s1 && s4 === s0 && s5 === s1
    && d.querySelector('#how-it-works [role="tablist"]') !== null && tRisk.textContent === "For risk & diligence teams" && tAg.textContent === "For AI agents & builders"
    && /claude mcp add --transport http pacta https:\/\/(?:pacta\.fractalneurons\.com|pacta-x402\.pacta\.workers\.dev)\/mcp/.test(pAg.textContent) && /cast call /.test(pAg.textContent)
    && pRisk.querySelectorAll('a[data-slot="button"]').map((a) => a.getAttribute("href")).join() === "scorecards/?grade=delta,radar/,scan/";
  // W3: Ctrl+K opens the command dialog; a ticker finds the protocol and its brief; arrows move; Enter would open; Escape closes; "/" reopens
  key(d.body, "k", { ctrlKey: true });
  const dlg = d.querySelector("[data-cmdk]"), qi = d.getElementById("cmdk-q");
  const opened = !!dlg && dlg.hidden === false && dlg.getAttribute("role") === "dialog" && dlg.getAttribute("aria-modal") === "true"
    && d.querySelector("[data-cmdk-open]").getAttribute("aria-expanded") === "true";
  qi.value = "lbtc"; const ie = new Event_("input"); ie.target = qi; qi.dispatchEvent(ie);
  for (let i = 0; i < 6; i++) await flush();
  const lb = d.querySelectorAll("#cmdk-list [data-cmdk-item]").map((a) => a.getAttribute("data-cmdk-item"));
  const firstSel = (d.querySelector('#cmdk-list [aria-selected="true"]') || { getAttribute: () => "" }).getAttribute("data-cmdk-item");
  key(qi, "ArrowDown"); const secondSel = (d.querySelector('#cmdk-list [aria-selected="true"]') || { getAttribute: () => "" }).getAttribute("data-cmdk-item");
  qi.value = "0xaafb31780e4b9c95bc920e388f4925a874cd07af"; qi.dispatchEvent(ie); for (let i = 0; i < 3; i++) await flush();
  const byAddr = d.querySelectorAll("#cmdk-list [data-cmdk-item]").map((a) => a.getAttribute("data-cmdk-item"));
  qi.value = "usdc"; qi.dispatchEvent(ie); for (let i = 0; i < 3; i++) await flush();
  const usdc = d.querySelectorAll("#cmdk-list [data-cmdk-item]").map((a) => a.getAttribute("data-cmdk-item"));
  key(qi, "Escape"); const closed = dlg.hidden === true && d.querySelector("[data-cmdk-open]").getAttribute("aria-expanded") === "false";
  key(d.body, "/"); const reopened = dlg.hidden === false; key(qi, "Escape");
  const inp = d.getElementById("pf-address"); key(inp, "/"); const notFromInput = dlg.hidden === true;
  res.v47_w3_cmdk = opened && lb[0] === "lombard-lbtc" && lb.includes("lombard-ops-0xceee-0x2f2a-0x6404") && firstSel === "lombard-lbtc" && secondSel === lb[1]
    && byAddr[0] === "stader-labs-ethx" && usdc[0] === "circle-usdc" && closed && reopened && notFromInput
    && d.querySelectorAll("#cmdk-list a").every((a) => /^https:\/\/pacta\.wtf\/(protocols|briefs)\/[a-z0-9-]+\/$/.test(a.getAttribute("href")));
  // W3: the hero checker resolves a name instead of rejecting it
  const pf = d.getElementById("pf-form"), out = d.getElementById("pf-out");
  inp.value = "Stader"; pf.dispatchEvent(new Event_("submit")); for (let i = 0; i < 4; i++) await flush();
  const item = out.querySelector('[data-pf-match-item="stader-labs-ethx"]');
  const named = !!item && inp.getAttribute("aria-invalid") === null && d.getElementById("pf-addr-error").hidden === true
    && /Open scorecard/.test(item.textContent) && item.querySelector("a").getAttribute("href") === "https://pacta.wtf/protocols/stader-labs-ethx/";
  item.querySelector("[data-pf-run]").dispatchEvent(new Event_("click")); for (let i = 0; i < 3; i++) await flush();
  const lkStader = input.lookupJson.items.find((x) => x.slug === "stader-labs-ethx").preflightArgs;
  const ran = inp.value === lkStader.address && d.getElementById("pf-chain").value === lkStader.chain && !out.querySelector("[data-pf-match-item]");
  inp.value = "zzqxj"; pf.dispatchEvent(new Event_("submit")); for (let i = 0; i < 3; i++) await flush();
  const none = !!out.querySelector("[data-pf-nomatch]") && inp.getAttribute("aria-invalid") === null;
  inp.value = "0x12"; pf.dispatchEvent(new Event_("submit")); await flush();
  res.v47_w3_hero_names = named && ran && none && inp.getAttribute("aria-invalid") === "true" && inp.getAttribute("maxlength") === "80";
  // W5: the theme button names the current choice; the mobile sheet row switches it (aria-pressed)
  const tl = d.querySelector("[data-theme-label]"), tb = d.querySelector("[data-theme-btn]");
  const sysOk = tl.textContent === "System" && tb.getAttribute("aria-label") === "Theme: System";
  const light = d.querySelectorAll("[data-theme-sheet]").find((b) => b.getAttribute("data-theme-set") === "light");
  light.dispatchEvent(new Event_("click"));
  res.v47_w5_theme_label = sysOk && tl.textContent === "Light" && tb.getAttribute("aria-label") === "Theme: Light" && light.getAttribute("aria-pressed") === "true"
    && d.querySelectorAll("[data-theme-sheet]").filter((b) => b.getAttribute("aria-pressed") === "true").length === 1
    && d.querySelectorAll('#theme-menu [role="menuitemradio"]').find((b) => b.getAttribute("data-theme-set") === "light").getAttribute("aria-checked") === "true"
    && p.document.documentElement.classList.contains("dark") === false;
}

// v4.7.1 V47-03: ?basket= (with underscores), ?grade= and ?q= select exactly what the manual controls select; unknown values are ignored
async function v471BasketScenario() {
  const scMock = (url) => /api\/v1\/scorecards\.json$/.test(String(url)) ? Promise.resolve({ status: 200, json: () => Promise.resolve(input.scorecardsJson) })
    : Promise.reject(new Error("not needed"));
  const cards = input.scorecardsJson.protocols;
  const want = (b, g, q) => cards.filter((c) => (!b || c.baskets.includes(b)) && (!g || c.grade === g) && (!q || String(c.search || "").includes(q))).length;
  const shown = async (search) => {
    const p = run(input.index, input.app, { path: "/", search, fetch: scMock });
    for (let i = 0; i < 6; i++) await flush();
    const d = p.document;
    return { n: d.querySelectorAll("#scorecards tr.sc-row").filter((r) => !r.hidden).length, basket: d.querySelector("[data-sc-basket]").value,
      pressed: (d.querySelectorAll("[data-sc-f]").find((b) => b.getAttribute("aria-pressed") === "true") || { getAttribute: () => "" }).getAttribute("data-sc-f") };
  };
  const out = {};
  for (const b of ["stable_rwa", "eth_lst_lrt", "lending_vaults", "base"]) out[b] = await shown("?basket=" + b);
  const combo = await shown("?basket=eth_lst_lrt&grade=delta&q=eth");
  const bogus = await shown("?basket=stable-rwa&grade=nope");
  res.v471_basket_urls = ["stable_rwa", "eth_lst_lrt", "lending_vaults", "base"].every((b) => out[b].n === want(b) && out[b].basket === b && out[b].n < cards.length)
    && out.stable_rwa.n === 69 && out.eth_lst_lrt.n === 46 && out.lending_vaults.n === 122 && out.base.n === 34
    && combo.n === want("eth_lst_lrt", "delta", "eth") && combo.n > 0 && combo.basket === "eth_lst_lrt" && combo.pressed === "delta"
    && bogus.n === 8 && bogus.pressed === "all";   // unknown values are ignored: the static 8-row preview stays
}

// v4.3 N5: after a live re-check the radar header still cites ONE block number (the finalized read); the live block goes on the
// provenance line under the table; the counts never read as a total ("Executed (N ops)")
async function radarHeaderScenario() {
  const fetchMock = (url) => {
    if (!/live-timelocks/.test(String(url))) return Promise.reject(new Error("not needed"));
    return Promise.resolve({ status: 200, json: () => Promise.resolve(live) });
  };
  let live = null;
  const p0 = run(input.index, input.app, { path: "/", fetch: () => Promise.reject(new Error("offline")) });
  // v4.6: rows tagged "Base" (chain id 8453) are re-read on Base; the live payload carries each op's chain and its own block
  const rows0 = p0.document.querySelectorAll("#radar tr[data-radar-row]");
  const ids = rows0.map((tr) => { const b = tr.querySelector("[data-ops]"); return ((b && b.getAttribute("data-ops")) || "").split(/\s+/).filter(Boolean); });
  const execRow = rows0.map((tr) => tr.getAttribute("data-radar-row"));
  const baseRow = rows0.map((tr) => !!tr.querySelector(".chain-tag"));
  const payload = (withBase) => ({ operations: ids.flatMap((g, i) => (baseRow[i] && !withBase ? [] : g).map((id) => ({ opId: id, chain: baseRow[i] ? "base" : "ethereum",
    live: execRow[i] === "executed" ? { status: "done", isOperationDone: true } : { status: execRow[i], isOperationPending: true, isOperationDone: false },
    block: { number: baseRow[i] ? 58999999 : 26999999 } }))) });
  const head0 = [".radar-head", ".livebar", "[data-radar-live]"].map((s) => (p0.document.querySelector("#radar " + s) || { textContent: "" }).textContent).join(" ");
  const blocks0 = head0.match(/#?\d{1,3}(,\d{3}){2,}/g) || [];
  live = payload(false);   // Ethereum operations only (e.g. a truncated live read): one Ethereum block
  const p = run(input.index, input.app, { path: "/", fetch: fetchMock });
  for (let i = 0; i < 6; i++) await flush();
  const d = p.document, head = [".radar-head", ".livebar", "[data-radar-live]"].map((s) => (d.querySelector("#radar " + s) || { textContent: "" }).textContent).join(" ");
  const blocks = head.match(/#?\d{1,3}(,\d{3}){2,}/g) || [];
  const pill = d.querySelector("#radar [data-prov-pill]"), asof = d.querySelector("#radar .livebar .lb-asof");
  res.v44_radar_live_pill = !!pill && pill.textContent === "Live-checked · #26,999,999" && !!asof && asof.hidden === true;
  const p0pill = p0.document.querySelector("#radar [data-prov-pill]"), p0asof = p0.document.querySelector("#radar .livebar .lb-asof");
  res.v44_radar_pill_stays_pinned_offline = !!p0pill && /^Scanner-pinned \(L1( \+ Base)? finalized\)$/.test(p0pill.textContent) && !!p0asof && p0asof.hidden !== true;
  // N5: the header still cites only the finalized read (one block per chain on the radar), never the live block
  res.v43_n5_radar_header_one_block = blocks.length >= 1 && blocks.length === blocks0.length && blocks.every((b, i) => b === blocks0[i])
    && blocks.length === (baseRow.some(Boolean) ? 2 : 1) && !/26,999,999|58,999,999/.test(head) && /finalized block #[\d,]+/.test(head)
    && d.querySelector("[data-live-status-text]").textContent === "Live state confirmed at the latest block"
    && d.querySelector("#radar [data-live-line]").textContent === "Live re-check at the latest block #26,999,999 via the free /v1/briefs/live-timelocks."
    && (execRow.includes("executed") ? / · Executed \(\d+ ops?\)$|^Executed \(\d+ ops?\)$/ : /^(?!.*Executed)/).test(d.querySelector("[data-radar-counts]").textContent)
    && !/operations\)/.test(d.querySelector("[data-radar-counts]").textContent);
  // v4.6: a two-chain live read: Ethereum and Base blocks are kept apart (the Base block never becomes the "latest block")
  live = payload(true);
  const q = run(input.index, input.app, { path: "/", fetch: fetchMock });
  for (let i = 0; i < 6; i++) await flush();
  const qd = q.document, qpill = qd.querySelector("#radar [data-prov-pill]"), qline = qd.querySelector("#radar [data-live-line]");
  const qhead = [".radar-head", ".livebar", "[data-radar-live]"].map((s) => (qd.querySelector("#radar " + s) || { textContent: "" }).textContent).join(" ");
  const qBase = qd.querySelectorAll("#radar tr[data-radar-row]").filter((tr) => !!tr.querySelector(".chain-tag"));
  res.v46_live_blocks_per_chain = baseRow.some(Boolean) && !!qpill && qpill.textContent === "Live-checked · #26,999,999 · Base #58,999,999"
    && !!qline && qline.textContent === "Live re-check at the latest blocks Ethereum #26,999,999 and Base #58,999,999 via the free /v1/briefs/live-timelocks."
    && qBase.length === 1 && qBase.every((tr) => tr.querySelector("[data-ops]").getAttribute("data-live") === "1")
    && JSON.stringify(qhead.match(/#?\d{1,3}(,\d{3}){2,}/g) || []) === JSON.stringify(blocks0)
    && qd.querySelector("[data-radar-counts]").textContent === p0.document.querySelector("[data-radar-counts]").textContent;
}

// v4.4 R-V1 / P2-2 / R-V4: verdict, metrics, then the indexed docs-vs-chain record with its badge; one visible scope sentence; the
// methodology and limits collapsed; a "Try:" click brings the form (input + result) into view; runtime links end in an inline
// arrow icon (svg.i.ia, aria-hidden), never a raw arrow glyph
async function liveCardScenario() {
  const calls = [];
  const reply = { ...PF_EXAMPLE, verdict: "UNCLASSIFIED_CONTRACT_CONTROLLER", riskScore: 65, source: "live_rpc",
    assessment: { coverage: "indexed_verified", confidence: "medium", method: "Live bytecode + storage heuristic", limits: ["riskScore is a heuristic."] },
    catalogMatch: { slug: "stader-labs-ethx", name: "Stader Labs (ETHx)", url: "https://pacta.wtf/protocols/stader-labs-ethx/", classification: "parameter_delta",
      pinnedBlock: 26403676, whatDiffers: { changed: [{ parameter: "Safe threshold", observed: "3-of-6", documented: "3-of-5", classification: "parameter_delta" }],
        matched: [{ parameter: "Timelock delay", value: "7 d" }] } } };
  const fetchMock = (url) => {
    if (!/\/v1\/check\/preflight/.test(String(url))) return Promise.reject(new Error("not needed"));
    calls.push(String(url)); return Promise.resolve({ status: 200, json: () => Promise.resolve(reply) });
  };
  const p = run(input.index, input.app, { path: "/", fetch: fetchMock });
  const d = p.document, form = d.getElementById("pf-form"), out = d.getElementById("pf-out");
  const scrolled = [];
  form.scrollIntoView = (o) => scrolled.push(["form", o && o.block]);
  out.scrollIntoView = (o) => scrolled.push(["out", o && o.block]);
  const chip = d.querySelectorAll("[data-receipt]").find((b) => b.getAttribute("data-r-name") === "Stader ETHx");
  chip.dispatchEvent(new Event_("click"));
  for (let i = 0; i < 4; i++) await flush();
  const card = out.querySelector("[data-pf-result]"), kids = card ? card.children : [];
  const is = (k, sel) => k.closest(sel) === k, at = (sel) => kids.findIndex((k) => is(k, sel));
  const iVerdict = at(".pf-verdict-row"), iMetrics = at(".pf-metrics"), iMatch = at("[data-pf-match]"), iScope = at("[data-pf-scope]");
  const lim = card ? card.querySelector("details[data-pf-limits]") : null;
  const visibleText = card ? kids.filter((k) => !is(k, '[data-slot="accordion"]') && !is(k, ".live-verify")).map((k) => k.textContent).join(" ") : "";
  const dvc = card ? card.querySelector("[data-pf-dvc]") : null, scope = card ? card.querySelector("[data-pf-scope]") : null;
  res.v44_live_card_verdict_first = !!card && iVerdict === 1 && iMetrics === iVerdict + 1 && iMatch === iMetrics + 1 && iScope === iMatch + 1
    && !!dvc && dvc.textContent === "Docs vs chain: Docs differ" && dvc.getAttribute("data-variant") === "warning"
    && scope.textContent === "The verdict and heuristic score cover only this one contract address (" + reply.address.slice(0, 6) + "…"
       + reply.address.slice(-4) + "), not the whole protocol."
    && !!lim && lim.getAttribute("open") === null && lim.querySelector("summary").textContent === "Methodology & single-address scope limits"
    && lim.textContent.includes("Limits: riskScore is a heuristic.") && lim.textContent.includes("Confidence medium")
    && !visibleText.includes("Limits:") && card.querySelectorAll("[data-pf-scope]").length === 1 && calls.length === 1;
  res.v44_try_scrolls_form = scrolled.length === 1 && scrolled[0][0] === "form" && scrolled[0][1] === "start";
  // F3a: the examples sit between the form and the result (a rendered result never moves them); F3b: no raw enum outside the raw JSON
  const pfKids = form.parentNode.children, tryBox = d.querySelector(".try");
  res.v44_examples_between_form_and_result = !!tryBox && tryBox.parentNode === form.parentNode
    && pfKids.indexOf(form) < pfKids.indexOf(tryBox) && pfKids.indexOf(tryBox) < pfKids.indexOf(out);
  const raw = card ? card.querySelector("[data-pf-raw]") : null;
  const shown = card ? card.textContent.replace(raw ? raw.textContent : "", "") : "";
  res.v44_no_raw_enums_in_result = !!card && !!raw && !/parameter_delta|protective_delta|aligned_baseline|rpc_observed|multisig_safe|access_control/.test(shown)
    && raw.textContent.includes("parameter_delta") && /Chain \/ block(Base|Ethereum) · block/.test(shown);
  const rec = out.querySelectorAll("a").find((a) => a.textContent === "Full record");
  const svg = rec ? rec.querySelector("svg") : null;
  res.v44_runtime_link_arrow_icon = !!svg && svg.getAttribute("class") === "i ia" && svg.getAttribute("aria-hidden") === "true"
    && !!svg.querySelector("path") && !/[\u2192\u2197\u2713\u2260]/.test(out.textContent);
}

// v4.4 (F6): the scope brief does not repeat the address (it is in the card header); the Gmail body starts at the track; "Copy brief
// and address" prefixes the address; the secondary actions are all outline buttons
async function requestBriefScenario() {
  const p = run(input.request, input.app, { path: "/request/" });
  for (let i = 0; i < 3; i++) await flush();
  const d = p.document, b = d.getElementById("req-brief").textContent, gm = d.getElementById("req-gmail"), cp = d.getElementById("req-copy");
  const body = decodeURIComponent((gm.getAttribute("href") || "").split("&body=")[1] || "");
  res.v44_request_brief_no_to = /^Subject: /.test(b) && !/^To: /m.test(b) && /^Track: /.test(body)
    && cp.getAttribute("data-copy-prefix") === "To: pacta@dri.network"
    && ["req-gh", "req-gmail", "req-copy"].every((id) => d.getElementById(id).getAttribute("data-variant") === "outline");
}

// v4.5: search and the /request/ combobox find a protocol by any of its contract addresses (the hero Try targets included); the
// homepage keeps 10 of its 16 static rows back below 640 px until any interaction; the combobox ranks prefix matches first and a
// mouse pick closes it; catalogMatch lines stay <= 140 characters and name the Safe a threshold belongs to; the limits link to
// /methodology/#live-checker
async function v45Scenario() {
  const TRY = { "stader-labs-ethx": "0xa35b1b31ce002fbf2058d22f30f95d405200a15b", "yo-protocol": "0xb4b3f5c964a360bbd7201f72a55d0c48b8ad7021",
    "moonwell-lending-base": "0xfbb21d0380bee3312b33c4353c8936a0f13ef26c" };
  const scMock = (url) => /api\/v1\/scorecards\.json/.test(String(url)) && input.scorecardsJson
    ? Promise.resolve({ status: 200, json: () => Promise.resolve(input.scorecardsJson) }) : Promise.reject(new Error("not needed"));
  let p = run(input.index, input.app, { path: "/", fetch: scMock });
  let d = p.document;
  const body = d.querySelector("[data-sc-body]"), staticRows = d.querySelectorAll("#scorecards tr.sc-row");
  const sixFirst = staticRows.length === 8 && staticRows.every((r) => !r.classList.contains("sc-m")) && !body.hasAttribute("data-all");   // v4.7: all 8 shown
  const q = d.getElementById("sc-q"), found = {};
  for (const [slug, a] of Object.entries(TRY)) {
    q.value = a; const ev = new Event_("input"); ev.target = q; q.dispatchEvent(ev);
    for (let i = 0; i < 4; i++) await flush();
    found[slug] = d.querySelectorAll("#scorecards tr.sc-row").filter((r) => !r.hidden).map((r) => r.getAttribute("data-slug")).join(",");
  }
  res.v45_search_finds_try_addresses = Object.entries(found).every(([slug, v]) => v === slug);
  res.v45_mobile_six_then_all = sixFirst && body.hasAttribute("data-all");
  // /request/ combobox
  p = run(input.request, input.app, { path: "/request/" });
  d = p.document;
  const ci = d.getElementById("req-proto-q"), list = d.getElementById("req-proto-list");
  const type = async (v) => { ci.value = v; const ev = new Event_("input"); ev.target = ci; ci.dispatchEvent(ev); await flush(); };
  const shown = () => list.querySelectorAll('[role="option"]').filter((o) => !o.hidden).map((o) => o.getAttribute("data-name"));
  await type("stad");
  const stad = shown();
  await type(TRY["stader-labs-ethx"]);
  const byAddr = shown();
  const opt = list.querySelectorAll('[role="option"]').find((o) => o.getAttribute("data-name") === "Stader Labs (ETHx)");
  const ck = new Event_("click"); ck.target = opt; list.dispatchEvent(ck); await flush();
  res.v45_combobox_prefix_address_click = stad[0] === "Stader Labs (ETHx)" && stad.includes("Fluid / Instadapp")
    && stad.indexOf("Stader Labs (ETHx)") < stad.indexOf("Fluid / Instadapp")
    && byAddr.length === 1 && byAddr[0] === "Stader Labs (ETHx)"
    && ci.getAttribute("aria-expanded") === "false" && ci.value === "" && list.hidden === true
    && d.querySelectorAll("[data-combo-chips] .chip-x").length === 1 && opt.getAttribute("aria-selected") === "true";
  // catalogMatch lines (the live Moonwell response shape) + the methodology link in the collapsed limits
  const reply = { ...PF_EXAMPLE, verdict: "UNCLASSIFIED_CONTRACT_CONTROLLER", riskScore: 60, source: "live_rpc",
    catalogMatch: { slug: "moonwell-lending-base", name: "Moonwell Lending (Base)", url: "https://pacta.wtf/protocols/moonwell-lending-base/",
      classification: "mixed", pinnedBlock: 57842915, whatDiffers: {
        changed: [{ classification: "parameter_delta", recordId: "moonwell-pause-guardian-2of4-safe-s18",
          parameter: "Comptroller pauseGuardian = 2-of-4 Safe (Constitution: pause = Security Council 3-of-5)",
          observed: "Unitroller (0xfBb21d0380beE3312B33c4353c8936a0F13EF26C).pauseGuardian() = 2-of-4 Safe 0x5B710010586C1b728B047c3E42473c700eeA4026 (v1.4.1);",
          documented: "Moonwell DAO Constitution 8.1: 'The Security Council has the power to execute any pause functionality, or perform other required actions with no delay ..." }],
        matched: [{ parameter: "Safe threshold", recordId: "moonwell-pause-guardian-2of4-safe-s18", value: "3-of-5" },
          { parameter: "Unitroller admin = TemporalGovernor (24h proposal delay), owned by the 3-of-5 Security Council",
            recordId: "moonwell-temporal-governor-24h-security-council-3of5-s18", value: "matches the documentation" }] } } };
  const pfMock = (url) => /\/v1\/check\/preflight/.test(String(url)) ? Promise.resolve({ status: 200, json: () => Promise.resolve(reply) })
    : Promise.reject(new Error("not needed"));
  p = run(input.index, input.app, { path: "/", fetch: pfMock });
  d = p.document;
  const f = d.getElementById("pf-form");
  f.querySelector('input[name="address"]').value = "0xfBb21d0380beE3312B33c4353c8936a0F13EF26C"; f.dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 4; i++) await flush();
  const out = d.getElementById("pf-out"), lines = (sel) => out.querySelectorAll(sel).map((x) => x.textContent);
  const ch = lines("[data-pf-changed]"), mt = lines("[data-pf-matched]");
  res.v45_catalog_lines = ch.length === 1 && ch[0] === "Changed: Comptroller pauseGuardian = 2-of-4 Safe (Constitution: pause = Security Council 3-of-5)"
    && mt[0] === "Matched: Security Council Safe threshold 3-of-5" && mt.length === 2 && ch.concat(mt).every((x) => x.length <= 140)
    && !!out.querySelector("[data-pf-dvc]") && out.querySelector("[data-pf-dvc]").textContent === "Docs vs chain: Docs differ";
  const ml = out.querySelectorAll("details[data-pf-limits] a").find((a) => a.textContent === "How the heuristic score differs from Docs vs chain");
  res.v45_live_checker_link = !!ml && ml.getAttribute("href") === "https://pacta.wtf/methodology/#live-checker"
    && out.textContent.includes("Heuristic score") && !out.textContent.includes("Risk score");
}

// (q) Option B v2: one product per page (/scan/, /webhook/, /seal/): exact amount + EIP-681 link, ONE primary action (a browser-wallet
//     transfer, or the manual drawer without a wallet), the order frozen at Pay, every control locked in flight, the API's order codes
async function checkoutScenario() {
  const C = input.checkout;
  if (!C || !input.scan || !input.webhook || !input.seal) { res.co_error = "no checkout input"; return; }
  const eip = (a) => "ethereum:" + C.usdc + "@8453/transfer?address=" + C.treasury + "&uint256=" + a;
  const pad = (h) => h.padStart(64, "0");
  const ADDR = "0x" + "12".repeat(20), TXH = "0x" + "cd".repeat(32);
  const submit = (d) => { const ev = new Event_("submit"); d.getElementById("co-form").dispatchEvent(ev); return ev; };
  const setv = (d, id, v) => { d.getElementById(id).value = v; };
  const page = (tree, path, o) => run(tree, input.app, Object.assign({ path }, o || {}));
  let calls = [];
  const okFetch = (status, body) => (url, opts) => {
    calls.push([url, opts]);
    return Promise.resolve({ status, ok: status === 200, text: () => Promise.resolve(typeof body === "string" ? body : JSON.stringify(body)),
                             json: () => Promise.resolve(typeof body === "string" ? {} : body) });
  };
  const shape = (d, sku) => {
    const f = d.getElementById("co-form"), m = d.getElementById("co-manual");
    return !!f && f.getAttribute("data-sku") === sku && d.querySelectorAll('input[name="sku"]').length === 0
      && d.querySelector("[data-co-amount]").textContent === C.amounts[sku] + " USDC"
      && d.querySelector("[data-co-eip681]").getAttribute("href") === eip(C.skus[sku])
      && d.getElementById("co-wallet").hidden === false && !m.hasAttribute("open") && d.getElementById("co-result").hidden === true;
  };
  const scanDoc0 = page(input.scan, "/scan/").document, sealDoc0 = page(input.seal, "/seal/").document;
  res.co_single_sku_pages = shape(page(input.webhook, "/webhook/").document, "radar-webhook-49")
    && !scanDoc0.getElementById("co-form") && !sealDoc0.getElementById("co-form");
  // no browser wallet (/webhook/): the primary action checks the order first, then opens the manual transfer drawer (never a dead button)
  calls = [];
  let p = page(input.webhook, "/webhook/", { fetch: okFetch(200, {}) }), d = p.document;
  click(d.getElementById("co-wallet"));
  const blocked = !d.getElementById("co-manual").hasAttribute("open") && d.getElementById("co-target-err").hidden === false;
  setField(d, "co-watch", ADDR); setv(d, "co-contact", "https://hooks.example.invalid/w"); click(d.getElementById("co-wallet"));
  res.co_no_wallet_opens_drawer = blocked && d.getElementById("co-manual").hasAttribute("open")
    && /No browser wallet/.test(d.getElementById("co-status").textContent) && calls.length === 0;
  // /scan/ free chip + /webhook/ quick-pick order flow
  calls = [];
  p = page(input.scan, "/scan/", { fetch: okFetch(200, { verdict: "IMMUTABLE_NO_ADMIN", chain: "ethereum", address: ADDR, pinnedBlock: 1, riskScore: 0 }) }); d = p.document;
  const chip = d.querySelectorAll("[data-receipt]")[0], chipAddr = chip.getAttribute("data-pf-address");
  click(chip); await flush(); await flush();
  const pfCall = calls.find((c) => /\/v1\/check\/preflight\?/.test(String(c[0])));
  const scanChipOk = d.getElementById("pf-address").value === chipAddr && !!pfCall && String(pfCall[0]).includes(chipAddr);
  calls = [];
  p = page(input.webhook, "/webhook/", { fetch: okFetch(200, { order_id: "ord_chip" }) }); d = p.document;
  const wPick = d.querySelectorAll("[data-co-pick]")[0], wPickAddr = wPick.getAttribute("data-address");
  click(wPick); setv(d, "co-contact", "https://hooks.example.invalid/pick"); setv(d, "co-tx", TXH);
  submit(d); await flush(); await flush();
  const post = calls.find((c) => c[0] === C.api);
  res.co_scan_chip_previews_and_orders = scanChipOk && !!post && JSON.parse(post[1].body).target_address === wPickAddr && JSON.parse(post[1].body).sku === "radar-webhook-49";
  // the exact contract body; the result is text only
  calls = [];
  const okBody = { order_id: "ord_harness_1", status: "verified <img src=x onerror=alert(1)>", report: { proxy_admin: "0x" + "ef".repeat(20) } };
  p = page(input.webhook, "/webhook/", { fetch: okFetch(200, okBody) }); d = p.document;
  setv(d, "co-chain", "base"); setField(d, "co-watch", ADDR); setv(d, "co-docs", "https://docs.example.invalid"); setv(d, "co-contact", "https://hooks.example.invalid/a"); setv(d, "co-tx", TXH);
  submit(d); await flush(); await flush();
  const b0 = calls[0] ? JSON.parse(calls[0][1].body) : null;
  res.co_verify_posts_exact_body = calls.length === 1 && calls[0][0] === C.api && calls[0][1].method === "POST"
    && same(b0, { sku: "radar-webhook-49", tx_hash: TXH, chain: "base", target_chain: "base", target_address: ADDR, protocol_or_docs: "https://docs.example.invalid", webhook_or_contact: "https://hooks.example.invalid/a" });
  const out = d.getElementById("co-result"), payA = out.querySelector("[data-co-r-pay] a");
  res.co_result_text_only = out.hidden === false && d.querySelector("[data-co-r-order]").textContent === "ord_harness_1"
    && d.querySelector("[data-co-r-status]").textContent.includes("<img src=x") && out.querySelectorAll("img").length === 0
    && d.getElementById("co-json").textContent.includes('"proxy_admin"') && !!payA && payA.getAttribute("href") === "https://basescan.org/tx/" + TXH;
  // the Worker's order codes: poll codes keep the order locked and waiting; final codes unlock with a specific message
  const codeRun = async (status, error) => {
    calls = [];
    const q = page(input.webhook, "/webhook/", { fetch: okFetch(status, error === null ? "Not Found" : { error }) }), qd = q.document;
    setField(qd, "co-watch", ADDR); setv(qd, "co-contact", "https://hooks.example.invalid/c"); setv(qd, "co-tx", TXH); submit(qd); await flush(); await flush();
    return { st: qd.getElementById("co-status").textContent, locked: qd.getElementById("co-verify").disabled === true, shown: qd.getElementById("co-result").hidden === false, n: calls.length };
  };
  const polls = [[425, "tx_not_confirmed"], [404, "tx_not_found"], [502, "order_rpc_unavailable"], [503, "order_not_recorded"], [503, "report_unavailable"], [409, "payment_in_progress"]];
  const finals = [[402, "insufficient_amount", /below the price/], [402, "tx_failed", /failed on Base/], [409, "providers_disagree", /disagree/],
    [409, "tx_already_used", /already unlocked/], [400, "invalid_order", /refused the request/], [503, "orders_unavailable", /unavailable right now/],
    [404, null, /not available yet/]];
  let pollsOk = true, finalsOk = true;
  for (const [st_, er_] of polls) { const r_ = await codeRun(st_, er_); pollsOk = pollsOk && r_.n === 1 && r_.locked && !r_.shown && /Waiting for Base/.test(r_.st); }
  for (const [st_, er_, re_] of finals) { const r_ = await codeRun(st_, er_); finalsOk = finalsOk && r_.n === 1 && !r_.locked && !r_.shown && re_.test(r_.st); }
  res.co_contract_codes = pollsOk && finalsOk;
  p = page(input.webhook, "/webhook/", { fetch: () => Promise.reject(new Error("offline")) }); d = p.document;
  setField(d, "co-watch", ADDR); setv(d, "co-contact", "https://hooks.example.invalid/o"); setv(d, "co-tx", TXH); submit(d); await flush(); await flush();
  res.co_errors_reported = /Could not reach the verifier/.test(d.getElementById("co-status").textContent) && d.getElementById("co-result").hidden === true;
  // wallet (/webhook/): switch to Base, ONE eth_sendTransaction = USDC.transfer(treasury, exact amount), then the frozen order is verified
  const wcalls = [];
  let chain = "0x1";
  const eth = { request: (a) => {
    wcalls.push(a);
    if (a.method === "eth_requestAccounts") return Promise.resolve(["0x" + "ab".repeat(20)]);
    if (a.method === "eth_chainId") return Promise.resolve(chain);
    if (a.method === "wallet_switchEthereumChain") { chain = a.params[0].chainId; return Promise.resolve(null); }
    if (a.method === "eth_sendTransaction") return Promise.resolve(TXH);
    return Promise.reject(Object.assign(new Error("unexpected"), { code: -1 }));
  } };
  calls = [];
  p = page(input.webhook, "/webhook/", { win: { ethereum: eth }, fetch: okFetch(200, { order_id: "ord_w" }) }); d = p.document;
  setField(d, "co-watch", ADDR); setv(d, "co-contact", "https://hooks.example.invalid/team"); click(d.getElementById("co-wallet"));
  for (let i = 0; i < 8; i++) await flush();
  const send = wcalls.find((a) => a.method === "eth_sendTransaction");
  const want = "0xa9059cbb" + pad(C.treasury.slice(2).toLowerCase()) + pad(C.skus["radar-webhook-49"].toString(16));
  const body1 = calls[0] ? JSON.parse(calls[0][1].body) : {};
  res.co_wallet_transfer_only = wcalls.some((a) => a.method === "wallet_switchEthereumChain" && a.params[0].chainId === "0x2105")
    && !!send && same(send.params, [{ from: "0x" + "ab".repeat(20), to: C.usdc, value: "0x0", data: want }])
    && wcalls.filter((a) => a.method === "eth_sendTransaction").length === 1 && !wcalls.some((a) => /approve|allowance|sign/i.test(a.method))
    && d.getElementById("co-tx").value === TXH && calls.length === 1 && body1.tx_hash === TXH && body1.sku === "radar-webhook-49"
    && body1.target_address === ADDR && body1.webhook_or_contact === "https://hooks.example.invalid/team";
  const eth2 = { request: (a) => a.method === "eth_sendTransaction" ? Promise.reject(Object.assign(new Error("denied"), { code: 4001 })) : eth.request(a) };
  chain = "0x2105"; calls = [];
  p = page(input.webhook, "/webhook/", { win: { ethereum: eth2 }, fetch: okFetch(200, {}) }); d = p.document;
  setField(d, "co-watch", ADDR); setv(d, "co-contact", "https://hooks.example.invalid/cancel"); click(d.getElementById("co-wallet")); for (let i = 0; i < 8; i++) await flush();
  res.co_wallet_cancel_sends_nothing = calls.filter((c) => c[0] === C.api).length === 0 && /Cancelled in the wallet/.test(d.getElementById("co-status").textContent)
    && d.getElementById("co-wallet").disabled === false && d.getElementById("co-watch").disabled === false;
  // one payment at a time, and the order frozen at Pay: while the prompt is open every control is locked;
  // a forced change during the prompt never reaches the POST; everything unlocks once it settles
  let release;
  const gate = new Promise((r) => { release = r; });
  const wc3 = [];
  const eth3 = { request: (a) => {
    wc3.push(a.method);
    if (a.method === "eth_requestAccounts") return gate.then(() => ["0x" + "ab".repeat(20)]);
    if (a.method === "eth_chainId") return Promise.resolve("0x2105");
    if (a.method === "eth_sendTransaction") return Promise.resolve(TXH);
    return Promise.reject(new Error("unexpected"));
  } };
  calls = [];
  p = page(input.webhook, "/webhook/", { win: { ethereum: eth3 }, fetch: okFetch(200, { order_id: "ord_once" }) }); d = p.document;
  setField(d, "co-watch", ADDR); setv(d, "co-docs", "https://docs.example.invalid/a"); setv(d, "co-contact", "https://hooks.example.invalid/once");
  const w3 = d.getElementById("co-wallet");
  click(w3); await flush(); click(w3); click(w3); await flush();
  const ids3 = ["co-wallet", "co-verify", "co-watch", "co-contact", "co-tx"];
  const locked3 = ids3.every((id) => d.getElementById(id).disabled === true) && d.querySelectorAll("[data-co-pick]").every((b) => b.disabled === true);
  setv(d, "co-target", "0x" + "99".repeat(20)); setv(d, "co-docs", "https://evil.example.invalid"); setv(d, "co-contact", "https://hooks.example.invalid/other");
  setv(d, "co-tx", TXH); submit(d); await flush();
  const noVerifyDuring = calls.filter((c) => c[0] === C.api).length === 0;
  release(); for (let i = 0; i < 8; i++) await flush();
  const posts3 = calls.filter((c) => c[0] === C.api), b3 = posts3[0] ? JSON.parse(posts3[0][1].body) : {};
  res.co_wallet_single_flight = locked3 && noVerifyDuring && wc3.filter((m) => m === "eth_requestAccounts").length === 1
    && wc3.filter((m) => m === "eth_sendTransaction").length === 1 && posts3.length === 1
    && ids3.every((id) => d.getElementById(id).disabled === false) && d.getElementById("co-result").hidden === false;
  res.co_snapshot_and_inputs_locked = locked3 && posts3.length === 1
    && same(b3, { sku: "radar-webhook-49", tx_hash: TXH, chain: "base", target_chain: "ethereum", target_address: ADDR, protocol_or_docs: "https://docs.example.invalid/a", webhook_or_contact: "https://hooks.example.invalid/once" });
  // /webhook/: quick picks fill the timelock / Safe and the protocol; the destination is required and must be https; empty fields stay out
  calls = [];
  p = page(input.webhook, "/webhook/", { fetch: okFetch(200, { order_id: "ord_w49" }) }); d = p.document;
  const picks = d.querySelectorAll("[data-co-pick]");
  const ethena = picks.find((b) => b.textContent === "Ethena"), aave = picks.find((b) => b.textContent === "Aave v3");
  click(ethena);
  const ethOk = /^0x[0-9a-fA-F]{40}$/.test(ethena.getAttribute("data-address")) && d.getElementById("co-target").value === ethena.getAttribute("data-address")
    && d.getElementById("co-docs").value === ethena.getAttribute("data-protocol") && ethena.getAttribute("aria-pressed") === "true";
  const watchEl = d.getElementById("co-watch"), hintEl = d.querySelector("[data-co-watch-hint]");
  const watchPick = !!watchEl && watchEl.value === ethena.getAttribute("data-protocol") && !/0x[0-9a-fA-F]{40}/.test(watchEl.value)
    && hintEl.textContent.indexOf(ethena.getAttribute("data-address").slice(0, 6) + "…") !== -1;
  setField(d, "co-watch", ADDR);
  const typedAddr = d.getElementById("co-target").value === ADDR && d.getElementById("co-docs").value === "" && ethena.getAttribute("aria-pressed") === "false";
  setField(d, "co-watch", "Morpho");
  const typedName = d.getElementById("co-target").value === "" && d.getElementById("co-docs").value === "Morpho";
  setField(d, "co-watch", "0x12"); setv(d, "co-contact", "https://hooks.example.invalid/x"); setv(d, "co-tx", TXH); submit(d); await flush();
  const badAddr = calls.length === 0 && d.getElementById("co-target-err").hidden === false && watchEl.getAttribute("aria-invalid") === "true";
  res.co_webhook_single_target = watchPick && typedAddr && typedName && badAddr
    && d.getElementById("co-target").getAttribute("type") === "hidden" && d.getElementById("co-docs").getAttribute("type") === "hidden";
  click(aave);
  const aaveOk = d.getElementById("co-target").value === "" && d.getElementById("co-docs").value === aave.getAttribute("data-protocol") && ethena.getAttribute("aria-pressed") === "false";
  setv(d, "co-contact", "http://hooks.example.invalid/x"); setv(d, "co-tx", TXH); submit(d); await flush();
  const httpRefused = calls.length === 0 && d.getElementById("co-contact-err").hidden === false;
  setv(d, "co-contact", ""); submit(d); await flush();
  const contactNeeded = calls.length === 0 && /alerts should go/.test(d.getElementById("co-contact-err").textContent);
  setv(d, "co-contact", "https://hooks.example.invalid/x"); submit(d); await flush(); await flush();
  res.co_webhook_picks_and_rules = ethOk && aaveOk && httpRefused && contactNeeded && calls.length === 1
    && same(JSON.parse(calls[0][1].body), { sku: "radar-webhook-49", tx_hash: TXH, chain: "base", target_chain: "ethereum", protocol_or_docs: aave.getAttribute("data-protocol"),
                                             webhook_or_contact: "https://hooks.example.invalid/x" });
  // /seal/?protocol=<slug>: reframed 3-path Base-EAS attestation page syncs protocol query into community & dossier links
  p = page(input.seal, "/seal/", { search: "?protocol=stader-labs-ethx" }); d = p.document;
  for (let i = 0; i < 3; i++) await flush();
  const sealComm = d.querySelector("[data-seal-community-link]"), sealDos = d.querySelector("[data-seal-dossier-link]");
  res.co_seal_protocol_prefill = !!sealComm && sealComm.getAttribute("href") === "../request/?tier=community&protocol=stader-labs-ethx"
    && !!sealDos && sealDos.getAttribute("href") === "../request/?tier=clearance&protocol=stader-labs-ethx";
  // /request/?tier=seal-99 | wallet-9 | webhook-49 forward cleanly; enterprise tiers stay on /request/
  const lr = run(input.request, input.app, { path: "/request/", search: "?tier=seal-99&protocol=stader-labs-ethx" });
  const lrScan = run(input.request, input.app, { path: "/request/", search: "?tier=wallet-9&protocol=stader-labs-ethx" });
  const lrWeb = run(input.request, input.app, { path: "/request/", search: "?tier=webhook-49&protocol=stader-labs-ethx" });
  const lr2 = run(input.request, input.app, { path: "/request/", search: "?tier=clearance" });
  res.co_request_launcher_forward = lr.location.replaced === "../seal/?protocol=stader-labs-ethx"
    && lrScan.location.replaced === "../scan/?protocol=stader-labs-ethx"
    && lrWeb.location.replaced === "../webhook/?protocol=stader-labs-ethx"
    && !lr2.location.replaced
    && lr.document.querySelectorAll("[data-launcher] a").length === 3;
  // Mobile WebView 1-tap wallet deep-links (/webhook/): shown ONLY when !window.ethereum and mobile UA;
  // strips staging /website-test prefix from target pacta.wtf dApp URL, preserves ?chain=...&address=..., syncs edits, and fires cta_click
  const mobileUa = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.0.0 Mobile Safari/537.36";
  const webStage = JSON.parse(JSON.stringify(input.webhook));
  webStage[1]["data-base-path"] = "/website-test";
  const qsInit = "?chain=base&address=" + C.usdc;
  const mwWeb = run(webStage, input.app, { path: "/website-test/webhook/", search: qsInit, nav: { userAgent: mobileUa }, beacon: input.beacon });
  const mwDoc = mwWeb.document, dlWeb = mwDoc.getElementById("co-deeplinks");
  const mmA = mwDoc.querySelector("[data-co-metamask]"), cbA = mwDoc.querySelector("[data-co-coinbase]");
  const wantCanon = "/webhook/" + qsInit;
  const webInitOk = !!dlWeb && dlWeb.hidden === false && mwDoc.getElementById("co-form").getAttribute("data-mobile-webview") === "true"
    && mwDoc.getElementById("co-target").value === C.usdc
    && mmA.getAttribute("href") === "https://metamask.app.link/dapp/pacta.wtf" + wantCanon
    && cbA.getAttribute("href") === "https://go.cb-wallet.com/dapp?cb_url=" + encodeURIComponent("https://pacta.wtf" + wantCanon)
    && !mwDoc.getElementById("co-manual").hasAttribute("open");
  const bBefore = mwWeb.beacons.length;
  click(mmA); click(cbA);
  const ctaEvents = mwWeb.events().slice(bBefore).map((e) => e.e);
  setField(mwDoc, "co-watch", ADDR);
  const wantEdited = "/webhook/?chain=base&address=" + ADDR;
  const webEditOk = mmA.getAttribute("href") === "https://metamask.app.link/dapp/pacta.wtf" + wantEdited
    && cbA.getAttribute("href") === "https://go.cb-wallet.com/dapp?cb_url=" + encodeURIComponent("https://pacta.wtf" + wantEdited);
  const deskWeb = run(input.webhook, input.app, { path: "/webhook/", nav: { userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36" } });
  const injectedMobile = run(input.webhook, input.app, { path: "/webhook/", search: qsInit, nav: { userAgent: mobileUa }, win: { ethereum: eth } });
  res.co_mobile_webview_deeplinks = webInitOk && webEditOk && same(ctaEvents, ["cta_click", "cta_click"])
    && deskWeb.document.getElementById("co-deeplinks").hidden === true
    && injectedMobile.document.getElementById("co-deeplinks").hidden === true
    && injectedMobile.document.getElementById("co-target").value === C.usdc;

  // 3-Door Free Scan + Free 30-Day Watch Pilot (/scan/) + Self-Serve Verification Pool Reservation (/bounties/#sponsor-pool):
  const pilotCalls = [];
  const pilotFetch = (url, opts) => {
    const u = String(url);
    pilotCalls.push([u, opts]);
    if (u.includes("/v1/check/preflight")) {
      const mCh = /[?&]chain=(ethereum|base)/.exec(u), mAd = /[?&]address=(0x[0-9a-fA-F]{40})/.exec(u);
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({
        verdict: "ZERO_DELAY_ADMIN_UPGRADE",
        chain: mCh ? mCh[1] : "ethereum",
        address: mAd ? mAd[1] : C.usdc,
        pinnedBlock: 22000000,
        riskScore: 65
      }) });
    }
    if (u.includes("/v1/pilot/watch")) {
      const wRes = { ok: true, watch_id: "WCH-2026-test01" };
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(wRes), text: () => Promise.resolve(JSON.stringify(wRes)) });
    }
    if (u.includes("/v1/pilot/sponsor-pool")) {
      const pRes = { ok: true, pool_id: "POOL-2026-test01" };
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(pRes), text: () => Promise.resolve(JSON.stringify(pRes)) });
    }
    return Promise.resolve({ status: 200, ok: true, text: () => Promise.resolve("{}"), json: () => Promise.resolve({}) });
  };
  const coldScan = page(input.scan, "/scan/", { search: "?internal=1&utm_source=x", fetch: pilotFetch }), cd = coldScan.document;
  const wpBox = cd.getElementById("watch-pilot"), wpTarget = cd.getElementById("watch-pilot-target"), wpDest = cd.getElementById("watch-pilot-dest");
  const privTxt = (cd.querySelector("[data-wp-privacy]") || {}).textContent || "";
  const coldClean = !cd.getElementById("co-form") && !!wpBox && privTxt.includes("from Pacta (") && !privTxt.includes("Strategy desk") && privTxt.includes("pacta@dri.network");
  const usdcChip = cd.querySelectorAll("[data-receipt]").find((b) => b.getAttribute("data-pf-address") === C.usdc) || cd.querySelectorAll("[data-receipt]")[0];
  const chipA = usdcChip.getAttribute("data-pf-address"), chipCh = usdcChip.getAttribute("data-pf-chain");
  const wantTarget = usdcChip.getAttribute("data-pf-slug") || (chipCh + ":" + chipA);
  click(usdcChip); for (let i = 0; i < 5; i++) await flush();
  const syncedWatch = wpTarget.value === wantTarget;
  wpDest.value = "risk@example.org";
  cd.querySelector("[data-watch-pilot-form]").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 5; i++) await flush();
  const wpPost = pilotCalls.find((c) => c[0].includes("/v1/pilot/watch"));
  const wpBody = wpPost ? JSON.parse(wpPost[1].body) : {};
  const wpDoneOk = !!wpPost && wpBody.target === wantTarget && wpBody.channel === "email" && wpBody.internal === true
    && cd.querySelector("[data-wp-done]").hidden === false && cd.querySelector("[data-wp-done-msg]").textContent.includes("WCH-2026-test01");
  let spDoneOk = true;
  if (input.bounties) {
    const bPg = run(input.bounties, input.app, { path: "/bounties/", search: "?internal=1", fetch: pilotFetch }), bd = bPg.document;
    const spSec = bd.getElementById("sponsor-pool");
    bd.getElementById("sp-target").value = "maple-finance-v2-syrup";
    bd.getElementById("sp-contact").value = "@curator_ops";
    bd.getElementById("sponsor-pool-form").dispatchEvent(new Event_("submit"));
    for (let i = 0; i < 5; i++) await flush();
    const spPost = pilotCalls.find((c) => c[0].includes("/v1/pilot/sponsor-pool"));
    const spBody = spPost ? JSON.parse(spPost[1].body) : {};
    spDoneOk = !!spSec && spSec.getAttribute("data-sponsor-address") === ""
      && !!spPost && spBody.target === "maple-finance-v2-syrup" && spBody.tier === "pool-50" && spBody.internal === true
      && bd.querySelector("[data-sp-done]").hidden === false && bd.querySelector("[data-sp-done-msg]").textContent.includes("POOL-2026-test01");
  }
  res.co_progressive_scan_funnel = coldClean && syncedWatch && wpDoneOk && spDoneOk;
}

async function xPixelScenario() {
  const UWT = "https://static.ads-twitter.com/uwt.js";
  const ADDR = "0x" + "12".repeat(20), TXH = "0x" + "ef".repeat(32);
  const mobileUa = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.0.0 Mobile Safari/537.36";

  // 1. Host gate: pacta.wtf & pacta.fractalneurons.com inject uwt.js once + record config rjbqn;
  //    staging / localhost keep window.__pactaTwqEvents in memory with ZERO uwt.js script injection;
  //    404.html ([data-nf]) and rescued stripped-? URLs stay silent.
  const prodWtf = run(input.index, input.app, { path: "/", hostname: "pacta.wtf" });
  const prodCom = run(input.index, input.app, { path: "/", hostname: "pacta.fractalneurons.com" });
  const stageDri = run(input.index, input.app, { path: "/website-test/", hostname: "pacta.dri.network" });
  const localDev = run(input.index, input.app, { path: "/", hostname: "127.0.0.1" });
  const nfPage = run(input.notfound, input.app, { path: "/missing", hostname: "pacta.wtf" });
  const rescuedPage = run(input.index, input.app, { path: "/", hostname: "pacta.wtf", win: { pactaRescued: 1 } });
  const uwtCount = (p) => p.document.querySelectorAll('script[src="' + UWT + '"]').length;
  res.x_pixel_host_gate = same(prodWtf.window.__pactaTwqEvents, [["config", "rjbqn"]]) && uwtCount(prodWtf) === 1
    && prodWtf.document.querySelector('script[src="' + UWT + '"]').hasAttribute("async")
    && same(prodCom.window.__pactaTwqEvents, [["config", "rjbqn"]]) && uwtCount(prodCom) === 1
    && same(stageDri.window.__pactaTwqEvents, [["config", "rjbqn"]]) && uwtCount(stageDri) === 0
    && same(localDev.window.__pactaTwqEvents, [["config", "rjbqn"]]) && uwtCount(localDev) === 0
    && same(nfPage.window.__pactaTwqEvents, []) && uwtCount(nfPage) === 0
    && same(rescuedPage.window.__pactaTwqEvents, []) && uwtCount(rescuedPage) === 0;

  // 2. Lead (tw-rjbqn-rjhie) dedup: fires on valid live_checker_submit OR checkout CTA (#co-wallet, MetaMask/Coinbase deep-link,
  //    or manual transfer summary expand), never on invalid checker input, and at most ONCE per page load.
  const pfFetch = () => Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ verdict: "IMMUTABLE_NO_ADMIN", chain: "ethereum", address: ADDR, blockNumber: 1, riskScore: 0 }) });
  const pfPage = run(input.index, input.app, { path: "/", hostname: "127.0.0.1", fetch: pfFetch });
  const pfAddr = pfPage.document.getElementById("pf-address"), pfForm = pfPage.document.getElementById("pf-form");
  pfAddr.value = "0xbad"; pfForm.dispatchEvent(new Event_("submit"));
  const invalidNoLead = same(pfPage.window.__pactaTwqEvents, [["config", "rjbqn"]]);
  pfAddr.value = ADDR; pfForm.dispatchEvent(new Event_("submit"));
  pfForm.dispatchEvent(new Event_("submit"));
  await flush();
  const pfLeadOnce = same(pfPage.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  const ctaWallet = run(input.webhook, input.app, { path: "/webhook/", hostname: "127.0.0.1" });
  click(ctaWallet.document.getElementById("co-wallet"));
  click(ctaWallet.document.getElementById("co-wallet"));
  const walletLeadOnce = same(ctaWallet.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  const ctaDl = run(input.webhook, input.app, { path: "/webhook/", hostname: "127.0.0.1", nav: { userAgent: mobileUa } });
  click(ctaDl.document.querySelector("[data-co-metamask]"));
  click(ctaDl.document.querySelector("[data-co-coinbase]"));
  const dlLeadOnce = same(ctaDl.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  const ctaDrawer = run(input.webhook, input.app, { path: "/webhook/", hostname: "127.0.0.1" });
  click(ctaDrawer.document.querySelector("#co-manual summary"));
  click(ctaDrawer.document.querySelector("#co-manual summary"));
  const drawerLeadOnce = same(ctaDrawer.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  const ctaWatch = run(input.scan, input.app, { path: "/scan/", hostname: "127.0.0.1", fetch: () => Promise.resolve({ status: 200, ok: true, text: () => Promise.resolve('{"ok":true,"watch_id":"WCH-1"}') }) });
  ctaWatch.document.getElementById("watch-pilot-target").value = ADDR;
  ctaWatch.document.getElementById("watch-pilot-dest").value = "ops@example.org";
  ctaWatch.document.querySelector("[data-watch-pilot-form]").dispatchEvent(new Event_("submit"));
  await flush();
  const watchLeadOnce = same(ctaWatch.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  res.x_pixel_lead_dedup = invalidNoLead && pfLeadOnce && walletLeadOnce && dlLeadOnce && drawerLeadOnce && watchLeadOnce;

  // 3. Purchase (tw-rjbqn-rjhif): fires ONLY on /v1/orders/verify HTTP 200 when !internalCanary, Pacta-Idempotent-Replay !== "true",
  //    and orderId not yet in localStorage; sends { value: Number(usdPrice), currency: "USD", conversion_id: String(orderId) }.
  const storeMap = {};
  const sharedStorage = {
    getItem: (k) => Object.prototype.hasOwnProperty.call(storeMap, k) ? storeMap[k] : null,
    setItem: (k, v) => { storeMap[k] = String(v); },
    removeItem: (k) => { delete storeMap[k]; }
  };
  const makeVerifyFetch = (status, body, replayHdr) => () => Promise.resolve({
    status,
    ok: status === 200,
    headers: { get: (h) => (String(h).toLowerCase() === "pacta-idempotent-replay" ? (replayHdr || null) : null) },
    text: () => Promise.resolve(JSON.stringify(body)),
    json: () => Promise.resolve(body)
  });
  const submitWebhook = async (fetchFn, txHash) => {
    const pg = run(input.webhook, input.app, { path: "/webhook/", hostname: "127.0.0.1", storage: sharedStorage, fetch: fetchFn });
    setField(pg.document, "co-watch", ADDR);
    pg.document.getElementById("co-contact").value = "https://hooks.example.invalid/x";
    pg.document.getElementById("co-tx").value = txHash || TXH;
    pg.document.getElementById("co-form").dispatchEvent(new Event_("submit"));
    await flush(); await flush();
    return pg.window.__pactaTwqEvents;
  };
  const evReal49 = await submitWebhook(makeVerifyFetch(200, { orderId: "ord_real_49", status: "verified", internalCanary: false }), TXH);
  const evReloadSameOrder = await submitWebhook(makeVerifyFetch(200, { orderId: "ord_real_49", status: "verified", internalCanary: false }), TXH);
  const evCanary = await submitWebhook(makeVerifyFetch(200, { orderId: "ord_canary_1", status: "verified", internalCanary: true }), "0x" + "aa".repeat(32));
  const evReplay = await submitWebhook(makeVerifyFetch(200, { orderId: "ord_replay_1", status: "verified", internalCanary: false }, "true"), "0x" + "bb".repeat(32));
  const evSecond49 = await submitWebhook(makeVerifyFetch(200, { orderId: "ord_real_49b", status: "verified", internalCanary: false }), "0x" + "cc".repeat(32));

  res.x_pixel_purchase_rules = same(evReal49, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhif", { value: 49, currency: "USD", conversion_id: "ord_real_49" }]])
    && same(evReloadSameOrder, [["config", "rjbqn"]])
    && same(evCanary, [["config", "rjbqn"]])
    && same(evReplay, [["config", "rjbqn"]])
    && same(evSecond49, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhif", { value: 49, currency: "USD", conversion_id: "ord_real_49b" }]])
    && same(JSON.parse(storeMap["pacta-x-purchased"]), ["ord_real_49", "ord_real_49b"]);
}

async function miniAppScenario() {
  if (!input.miniapp || !input.checkout) { res.ma_error = "no miniapp input"; return; }
  const C = input.checkout;
  const UNIDX = "0x" + "77".repeat(20), TX19 = "0x" + "19".repeat(32), TX99 = "0x" + "99".repeat(32);
  const postedMsgs = [];
  const fakeParent = { postMessage: (msg, origin) => { postedMsgs.push([msg, origin]); } };

  // 1. Embedded Farcaster / Base App ready() postMessage handshake + EIP-5792 capability probe
  const wCalls = [];
  let chainId = "0x1";
  const eth = {
    isCoinbaseWallet: true,
    request: (a) => {
      wCalls.push(a);
      if (a.method === "wallet_getCapabilities") return Promise.resolve({ "0x2105": { atomicBatch: { supported: true } } });
      if (a.method === "eth_requestAccounts") return Promise.resolve(["0x" + "ab".repeat(20)]);
      if (a.method === "eth_chainId") return Promise.resolve(chainId);
      if (a.method === "wallet_switchEthereumChain") { chainId = a.params[0].chainId; return Promise.resolve(null); }
      if (a.method === "eth_sendTransaction") return Promise.resolve(chainId === "0x2105" && wCalls.filter((x) => x.method === "eth_sendTransaction").length === 1 ? TX19 : TX99);
      return Promise.reject(new Error("unexpected method " + a.method));
    }
  };
  const maFetch = (url, opts) => {
    const u = String(url);
    if (/api\/v1\/lookup\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(input.lookupJson) });
    if (u.includes("/v1/check/preflight")) {
      const addr = new URL(u).searchParams.get("address");
      const isUsdc = addr.toLowerCase() === C.usdc.toLowerCase();
      const isMoonwell = addr.toLowerCase() === "0xfbb21d0380bee3312b33c4353c8936a0f13ef26c";
      return Promise.resolve({
        status: 200,
        ok: true,
        json: () => Promise.resolve({
          verdict: isUsdc ? "MULTISIG_NO_TIMELOCK" : isMoonwell ? "TIMELOCK_PROTECTED" : "INSTANT_EOA_ADMIN_RISK",
          riskScore: isUsdc ? 40 : isMoonwell ? 20 : 90,
          summary: "Block-pinned authority check.",
          block: { number: 28000555 },
          controller: { kind: isUsdc ? "multisig_safe" : "eoa", address: "0x" + "33".repeat(20), safeThreshold: 2, safeOwnerCount: 3 }
        })
      });
    }
    if (u === C.api) {
      const body = JSON.parse(opts.body);
      const oid = body.sku === "instant-scan-19" ? "ord_ma_19" : "ord_ma_99";
      return Promise.resolve({
        status: 200,
        ok: true,
        headers: { get: () => null },
        text: () => Promise.resolve(JSON.stringify({ orderId: oid, status: "verified", internalCanary: false })),
        json: () => Promise.resolve({ orderId: oid, status: "verified", internalCanary: false })
      });
    }
    return Promise.reject(new Error("unexpected fetch " + u));
  };

  const p = run(input.miniapp, input.app, { path: "/miniapp/", hostname: "127.0.0.1", win: { parent: fakeParent, ethereum: eth }, fetch: maFetch });
  for (let i = 0; i < 4; i++) await flush();
  res.ma_frame_ready_handshake = p.window.__pactaMiniAppReady === true
    && postedMsgs.some(([m]) => m && m.type === "fc:frame:ready")
    && p.document.getElementById("ma-root").getAttribute("data-eip5792") === "true"
    && /Coinbase Wallet Ready/.test(p.document.getElementById("ma-wallet-pill").textContent);

  // 2. Instant Free Check: ALIGNED (USDC preset), ADVERSE DELTA (Moonwell preset), UNINDEXED (custom 0x...)
  const presets = p.document.querySelectorAll("[data-ma-preset]");
  const usdcPreset = presets.find((b) => b.getAttribute("data-slug") === "circle-usdc");
  const mwPreset = presets.find((b) => b.getAttribute("data-slug") === "moonwell-lending-base");
  click(usdcPreset);
  for (let i = 0; i < 6; i++) await flush();
  const alignedOk = p.document.getElementById("ma-verdict").getAttribute("data-ma-status") === "ALIGNED"
    && p.document.getElementById("ma-v-badge").hidden === false
    && /circle-usdc\.svg$/.test(p.document.getElementById("ma-v-badge").getAttribute("src"));

  click(mwPreset);
  for (let i = 0; i < 6; i++) await flush();
  const deltaOk = p.document.getElementById("ma-verdict").getAttribute("data-ma-status") === "ADVERSE DELTA"
    && p.document.getElementById("ma-v-badge").hidden === false;

  p.document.getElementById("ma-address").value = UNIDX;
  p.document.getElementById("ma-check-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 6; i++) await flush();
  const unidxOk = p.document.getElementById("ma-verdict").getAttribute("data-ma-status") === "UNINDEXED"
    && p.document.getElementById("ma-v-badge").hidden === true;

  res.ma_instant_verdicts = alignedOk && deltaOk && unidxOk;

  // 3. 1-Tap Base USDC upgrades ($19 Scan & $99 Seal -> 0x2105 switch -> exact USDC transfer -> /v1/orders/verify -> X Purchase)
  click(p.document.getElementById("ma-buy-scan"));
  for (let i = 0; i < 8; i++) await flush();
  const scanUnlocked = p.document.getElementById("ma-receipt").hidden === false
    && p.document.getElementById("ma-r-order").textContent === "ord_ma_19";

  // $99 Seal requires contact first, then succeeds when contact is filled
  click(p.document.getElementById("ma-buy-seal"));
  const sealNeedsContact = p.document.getElementById("ma-contact-err").hidden === false;
  p.document.getElementById("ma-contact").value = "@founder";
  click(p.document.getElementById("ma-buy-seal"));
  for (let i = 0; i < 8; i++) await flush();
  const sealUnlocked = p.document.getElementById("ma-r-order").textContent === "ord_ma_99";
  const txCalls = wCalls.filter((x) => x.method === "eth_sendTransaction");

  res.ma_wallet_upgrade_19_and_99 = scanUnlocked && sealNeedsContact && sealUnlocked && txCalls.length === 2
    && txCalls[0].params[0].to === C.usdc && txCalls[1].params[0].to === C.usdc
    && p.window.__pactaTwqEvents.some((e) => e[1] === "tw-rjbqn-rjhif" && e[2].value === 19 && e[2].conversion_id === "ord_ma_19")
    && p.window.__pactaTwqEvents.some((e) => e[1] === "tw-rjbqn-rjhif" && e[2].value === 99 && e[2].conversion_id === "ord_ma_99");
}

async function pfComboboxScenario() {
  const pfCalls = [];
  const mockFetch = (url) => {
    const u = String(url);
    if (/api\/v1\/lookup\.json$/.test(u)) return Promise.resolve({ status: 200, json: () => Promise.resolve(input.lookupJson) });
    if (/api\/v1\/scorecards\.json$/.test(u)) return Promise.resolve({ status: 200, json: () => Promise.resolve(input.scorecardsJson) });
    if (/\/v1\/check\/preflight/.test(u)) {
      pfCalls.push(u);
      const mAddr = /[?&]address=(0x[0-9a-fA-F]{40})/.exec(u);
      const mCh = /[?&]chain=(base|ethereum)/.exec(u);
      return Promise.resolve({ status: 200, json: () => Promise.resolve(Object.assign({}, PF_EXAMPLE, {
        chain: mCh ? mCh[1] : PF_EXAMPLE.chain,
        address: mAddr ? mAddr[1] : PF_EXAMPLE.address
      })) });
    }
    return Promise.reject(new Error("unexpected fetch: " + u));
  };
  const p = run(input.scan, input.app, { path: "/scan/", fetch: mockFetch });
  const d = p.document, inp = d.getElementById("pf-address"), lb = d.getElementById("pf-listbox");
  const selChip = d.getElementById("pf-sel-chip"), clr = d.getElementById("pf-combo-clear");
  inp.dispatchEvent(new Event_("focus"));
  for (let i = 0; i < 5; i++) await flush();
  const opts0 = lb.querySelectorAll("[data-pf-opt]");
  const zeroTypeOk = lb.hidden === false && inp.getAttribute("aria-expanded") === "true" && opts0.length >= 15
    && opts0.every((o) => !!o.querySelector("img.pf-opt-logo") && !!o.querySelector(".pf-st-pill"));
  const typeQ = async (q) => {
    inp.value = q; const ev = new Event_("input"); ev.target = inp; inp.dispatchEvent(ev);
    for (let i = 0; i < 3; i++) await flush();
    return lb.querySelectorAll("[data-pf-opt]").map((o) => o.getAttribute("data-pf-opt"));
  };
  const stethHits = await typeQ("steth");
  const cakeHits = await typeQ("cake");
  const moonHits = await typeQ("moon");
  const tickerAndNameOk = stethHits[0] === "lido-steth-dual-governance" && cakeHits[0] === "pancakeswap-amm-v3"
    && moonHits[0] === "moonwell-lending-base";
  const moonOpt = lb.querySelector('[data-pf-opt="moonwell-lending-base"]');
  moonOpt.dispatchEvent(new Event_("click"));
  for (let i = 0; i < 5; i++) await flush();
  const mw = input.lookupJson.items.find((x) => x.slug === "moonwell-lending-base").preflightArgs;
  const selectedOk = lb.hidden === true && inp.getAttribute("aria-expanded") === "false"
    && d.getElementById("pf-chain").value === "base" && inp.value === mw.address
    && selChip.hidden === false && selChip.textContent.includes("Moonwell") && selChip.textContent.includes("WELL")
    && pfCalls.length === 1 && pfCalls[0].includes("chain=base&address=" + mw.address)
    && d.getElementById("watch-pilot-target").value === "moonwell-lending-base";
  clr.dispatchEvent(new Event_("click"));
  for (let i = 0; i < 3; i++) await flush();
  const clearedOk = inp.value === "" && selChip.hidden === true && lb.hidden === false;
  res.pf_combobox_select_and_autocomplete = zeroTypeOk && tickerAndNameOk && selectedOk && clearedOk;
}

async function internalQaScenario() {
  const ADDR = "0xa35b1b31ce002fbf2058d22f30f95d405200a15b";
  const makeStore = (init = {}) => {
    const map = Object.assign({}, init);
    const writes = [];
    return {
      map,
      writes,
      storage: {
        getItem: (k) => (Object.prototype.hasOwnProperty.call(map, k) ? map[k] : null),
        setItem: (k, v) => { writes.push(["set", k, String(v)]); map[k] = String(v); },
        removeItem: (k) => { writes.push(["rm", k]); delete map[k]; }
      }
    };
  };
  const pfUrls = [];
  const pfFetch = (url) => {
    const u = String(url);
    if (/\/v1\/check\/(?:preflight|wallet-exposure)/.test(u)) {
      pfUrls.push(u);
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(PF_EXAMPLE) });
    }
    return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ items: [] }) });
  };

  // 1. External visitor: 0 storage writes, no i field on beacons, caller_agent=pacta-wtf-checker, no footer badge
  const extStore = makeStore();
  const ext = run(input.scan, input.app, { path: "/scan/", hostname: "pacta.wtf", beacon: input.beacon, storage: extStore.storage, fetch: pfFetch });
  ext.document.getElementById("pf-address").value = ADDR;
  ext.document.getElementById("pf-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 4; i++) await flush();
  const extEv = ext.events();
  res.qa_external_untouched = extStore.writes.length === 0
    && ext.window.__pactaInternal === 0
    && extEv.length === 2 && !("i" in extEv[0]) && !("i" in extEv[1])
    && !!pfUrls[0] && pfUrls[0].includes("caller_agent=pacta-wtf-checker")
    && !ext.document.querySelector("[data-internal-qa-badge]");

  // 2. ?internal=1&utm_source=x: sets pacta_internal="1", strips internal=1 keeping ?utm_source=x, tags beacons i:1, sends caller_agent=pacta-founder-qa, renders footer badge + skips uwt.js & xTrackLead
  const qaStore = makeStore();
  const qa = run(input.scan, input.app, { path: "/scan/", search: "?internal=1&utm_source=x", hash: "#top", hostname: "pacta.wtf", beacon: input.beacon, storage: qaStore.storage, fetch: pfFetch });
  qa.document.getElementById("pf-address").value = ADDR;
  qa.document.getElementById("pf-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 4; i++) await flush();
  const qaEv = qa.events();
  const qaBadge = qa.document.querySelector("[data-internal-qa-badge]");
  res.qa_opt_in_persists_and_tags = qaStore.map.pacta_internal === "1"
    && qa.location.search === "?utm_source=x" && qa.location.hash === "#top"
    && qa.window.__pactaInternal === 1
    && qaEv.length === 2 && qaEv[0].e === "page_load" && qaEv[0].i === 1 && qaEv[1].e === "live_checker_submit" && qaEv[1].i === 1
    && pfUrls[1].includes("caller_agent=pacta-founder-qa")
    && !!qaBadge && qaBadge.textContent.includes("Internal QA mode active")
    && qa.document.querySelectorAll('script[src="https://static.ads-twitter.com/uwt.js"]').length === 0
    && !qa.window.__pactaTwqEvents.some((e) => e[0] === "event");

  // 3. Subsequent visit without ?internal=1 keeps QA mode active; clicking [Turn off] clears storage, hides badge, and stops tagging
  const nextVisit = run(input.scan, input.app, { path: "/scan/", hostname: "pacta.wtf", beacon: input.beacon, storage: qaStore.storage, fetch: pfFetch });
  const persistedOk = nextVisit.window.__pactaInternal === 1 && nextVisit.events()[0].i === 1 && !!nextVisit.document.querySelector("[data-internal-qa-badge]");
  const offBtn = nextVisit.document.querySelector("[data-internal-qa-off]");
  offBtn.dispatchEvent(new Event_("click"));
  nextVisit.window.scrollY = 3000;
  (nextVisit.winListeners.scroll || []).forEach((fn) => fn());
  const nextEv = nextVisit.events();
  res.qa_turn_off_and_param_zero = persistedOk
    && !("pacta_internal" in qaStore.map)
    && nextVisit.window.__pactaInternal === 0
    && nextVisit.document.querySelector("[data-internal-qa-badge]").hidden === true
    && nextEv.some((x) => x.e === "scroll_50" && !("i" in x));

  // 4. Visiting ?internal=0 clears persisted storage and strips ?internal=0
  const clearStore = makeStore({ pacta_internal: "1" });
  const cleared = run(input.scan, input.app, { path: "/scan/", search: "?internal=0", hostname: "pacta.wtf", beacon: input.beacon, storage: clearStore.storage });
  res.qa_param_zero_clears = !("pacta_internal" in clearStore.map)
    && cleared.location.search === ""
    && cleared.window.__pactaInternal === 0
    && !("i" in cleared.events()[0])
    && !cleared.document.querySelector("[data-internal-qa-badge]");
}

async function walletExposureScenario() {
  if (!input.scan || !input.walletTokensJson || !input.lookupJson) { res.wl_error = "missing walletTokensJson"; return; }
  const wt = input.walletTokensJson;
  const encodeRes3 = (items) => {
    const u = (n) => Number(n).toString(16).padStart(64, "0");
    let heads = "", tails = "", off = items.length * 32;
    for (const it of items) {
      const d = (it.data || "0x").slice(2).toLowerCase();
      const bLen = d.length / 2, rem = d.length % 64;
      const padD = rem === 0 ? d : d + "0".repeat(64 - rem);
      heads += u(off);
      const el = u(it.ok ? 1 : 0) + u(64) + u(bLen) + padD;
      tails += el;
      off += el.length / 2;
    }
    return "0x" + u(32) + u(items.length) + heads + tails;
  };
  const encodeStr = (s) => {
    const hex = Buffer.from(s, "utf8").toString("hex");
    return "0x" + (32).toString(16).padStart(64, "0") + s.length.toString(16).padStart(64, "0") + hex.padEnd(64, "0");
  };

  let rpcCalls = [], pfCalls = [], weCalls = [];
  const mockFetch = (url, opts) => {
    const u = String(url);
    if (/api\/v1\/wallet-tokens\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(wt) });
    if (/api\/v1\/lookup\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(input.lookupJson) });
    if (/api\/v1\/scorecards\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(input.scorecardsJson) });
    if (u.includes("/v1/check/preflight")) {
      pfCalls.push(u);
      const mAddr = /[?&]address=(0x[0-9a-fA-F]{40})/.exec(u);
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(Object.assign({}, PF_EXAMPLE, { address: mAddr ? mAddr[1] : PF_EXAMPLE.address })) });
    }
    if (u.includes("/v1/check/wallet-exposure")) {
      weCalls.push(u);
      return Promise.resolve({ status: 404, ok: false, json: () => Promise.resolve({ error: "not_found" }) });
    }
    if (/publicnode\.com|drpc\.org|mainnet\.base\.org/.test(u)) {
      const body = JSON.parse(opts.body);
      rpcCalls.push([u, body.method, body.params]);
      if (body.method === "eth_blockNumber") {
        return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ jsonrpc: "2.0", id: 1, result: u.includes("base") ? "0x3912abc" : "0x1939def" }) });
      }
      if (body.method === "eth_call") {
        const callObj = body.params[0] || {};
        const data = String(callObj.data || "");
        const len = parseInt(data.slice(74, 138), 16);
        const isBase = u.includes("base");
        // Pass 2 has len === 2 (1 hit * [symbol, decimals]); Pass 1 has len > 10
        if (len <= 6) {
          return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ jsonrpc: "2.0", id: 1, result: encodeRes3([
            { ok: true, data: encodeStr(isBase ? "mUSDC" : "ETHx") },
            { ok: true, data: "0x" + (isBase ? 6 : 18).toString(16).padStart(64, "0") }
          ]) }) });
        }
        const items = [];
        for (let i = 0; i < len; i++) {
          if (i === 0) items.push({ ok: true, data: "0x" + (2).toString(16).padStart(64, "0") });
          else if (i === 1) items.push({ ok: true, data: "0x" + (32).toString(16).padStart(64, "0") + (2).toString(16).padStart(64, "0") + "11".repeat(20).padStart(64, "0") + "22".repeat(20).padStart(64, "0") });
          else if (i === 5) items.push({ ok: true, data: "0x" + (isBase ? 25000000000n : 5000000000000000000n).toString(16).padStart(64, "0") });
          else items.push({ ok: true, data: "0x" + "0".repeat(64) });
        }
        return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ jsonrpc: "2.0", id: 1, result: encodeRes3(items) }) });
      }
    }
    return Promise.reject(new Error("unexpected url: " + u));
  };

  // 1. Demo Treasury Safe chip: 100% free full multi-position render (zero $9 lock) + inline 30-day Free Watch Pilot w/ privacy line
  const p = run(input.scan, input.app, { path: "/scan/", fetch: mockFetch });
  const d = p.document;
  const coldOk = !d.getElementById("co-form") && !d.querySelector("[data-wallet-locked]");
  const demoSafeBtn = d.querySelector('[data-wallet-demo="demo_safe_eth_base"]');
  click(demoSafeBtn);
  for (let i = 0; i < 6; i++) await flush();
  const hl = d.querySelector("[data-wallet-headline]");
  const safeBadge = d.querySelector("[data-wallet-safe-badge]");
  const topGap = d.querySelector("[data-wallet-top-gap]");
  const gapItems = d.querySelectorAll("[data-wallet-gap-item]").map((x) => x.getAttribute("data-wallet-gap-item"));
  const contagion = d.querySelector("[data-wallet-contagion]");
  const inlineWatch = d.querySelector("[data-wallet-watch-inline]");
  const b2bBar = d.querySelector("[data-wallet-b2b]");
  const demoOk = coldOk && !!hl && hl.textContent.includes("Found 4 active DeFi positions") && hl.textContent.includes("2 ALIGNED, 2 ADVERSE GAPS")
    && !!safeBadge && safeBadge.textContent.includes("Gnosis Safe 3-of-5")
    && !!topGap && topGap.getAttribute("data-wallet-top-gap") === "yo-protocol"
    && same(gapItems, ["yo-protocol", "stader-labs-ethx"])
    && !!contagion && contagion.textContent.includes("Exit-Window & Signer Overlap")
    && !!inlineWatch && inlineWatch.textContent.includes("pacta@dri.network")
    && !d.querySelector("[data-wallet-locked]") && !!b2bBar;

  // 2. Dispatch Rule 2: known protocol 0x contract -> single-protocol preflight + 1-click wallet deposit prompt
  const staderAddr = "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b";
  d.getElementById("pf-address").value = staderAddr;
  d.getElementById("pf-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 6; i++) await flush();
  const protoDispatchOk = pfCalls.length === 1 && pfCalls[0].includes(staderAddr)
    && !!d.querySelector("[data-wallet-proto-prompt]");

  // 3. Dispatch Rule 3: unknown wallet/Safe 0x -> /v1/check/wallet-exposure (404) -> browser-direct Multicall3.aggregate3 fallback
  click(d.querySelector("[data-focus-wallet-scan]"));
  const userWallet = "0x9999999999999999999999999999999999999999";
  d.getElementById("pf-address").value = userWallet;
  d.getElementById("pf-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 12; i++) await flush();
  const mcCalls = rpcCalls.filter((c) => c[1] === "eth_call" && String(c[2][0].to).toLowerCase() === "0xca11bde05977b3631167028862be2a173976ca11");
  const hlLive = d.querySelector("[data-wallet-headline]");
  const fallbackOk = weCalls.length === 1 && weCalls[0].includes(userWallet)
    && mcCalls.length >= 2 && !!hlLive && hlLive.textContent.includes("active DeFi position");

  res.wl_demo_and_multicall_fallback = demoOk && protoDispatchOk && fallbackOk;
}
(async () => {
  try { await v45Scenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await pfComboboxScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await internalQaScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await walletExposureScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await requestBriefScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await liveCardScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await tryExampleScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await radarHeaderScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await v47Scenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await v471BasketScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { protocolFilterScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await preflightScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await staleResponseScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await beaconScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { rescueScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await checkoutScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await xPixelScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await miniAppScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await liveTimelockScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await lateLivePayloadScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await basePathScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await visitorScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await liveRpcScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  res.v43_no_init_errors = INIT_ERRORS.length === 0;
  if (INIT_ERRORS.length) res.init_errors = INIT_ERRORS.slice(0, 3);
  process.stdout.write(JSON.stringify(res));
})();
