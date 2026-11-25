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
  clearance: "Custom Control-Plane Dossier (by arrangement)",
  api_sla: "Enterprise / High-Throughput API SLA (priced on scope)",
  community: "Free doc-update & post-fix queue (typically 6–8 weeks)"
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
  res.clearance_brief_has_price_and_invoice = /by arrangement/.test(brief(d)) && !/\$5,000|\$2,500/.test(brief(d)) && brief(d).includes("Settlement: Option A") && !brief(d).includes("Payment:")
    && /^0x[0-9a-fA-F]{40}$/.test(treasury || "") && !brief(d).includes(treasury);
  res.pay_summary_tracks_tier = d.getElementById("req-pay-sum").textContent === "Custom Control-Plane Dossier · by arrangement";
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
  // (e2) the API SLA track: own dropdown option, own amount in the summary and the Option B payment line (no alerts track exists)
  pick(d, "api_sla");
  q = ghParams(d);
  res.api_sla_track = q.get("package_tier") === OPT.api_sla && d.getElementById("req-pay").hidden === false
    && d.getElementById("req-pay-sum").textContent === "Enterprise / High-Throughput API SLA · priced on scope";
  // (f) ?tier=community prefill; legacy ?tier=rapid-500 forwards to the free doc-update queue (community) track; unknown tiers (incl. the retired
  //     Section 7 ?tier=wholesale-150) fall back to the default clearance dossier, by arrangement
  p = run(input.request, input.app, { path: "/request/", search: "?tier=community" });
  res.prefill_selects_community = checked(p.document) === "community" && p.document.getElementById("req-pay").hidden === true;
  p = run(input.request, input.app, { path: "/request/", search: "?tier=disclosure" });
  res.prefill_unknown_tier_keeps_clearance = checked(p.document) === "clearance";
  const pw = run(input.request, input.app, { path: "/request/", search: "?tier=wholesale-150" });
  p = run(input.request, input.app, { path: "/request/", search: "?tier=rapid-500" });
  res.prefill_rapid_500 = checked(pw.document) === "clearance"
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
    // Business 11 points: the retired alerts track: a legacy ?tier=continuous link opens the default dossier track, never an alerts offer
    res.prefill_legacy_continuous_falls_back = checked(xd) === "clearance" && settled(xd) === "invoice" && xq.get("package_tier") === OPT.clearance
      && xq.get("settlement_preference") === SET.invoice && fieldVal(xd, "req-forum") === "" && !/webhook alerts/i.test(brief(xd))
      && xd.querySelectorAll('input[name="tier"]').every((r) => r.value !== "continuous");
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
  res.pf_renders_verdict = txt.includes("MULTISIG_NO_TIMELOCK") && !txt.includes("Heuristic score") && !txt.includes("/100") && txt.includes("Safe multisig (3-of-5)") && txt.includes("pause, upgrade");
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
    res.b_cta_aligned_maintenance = same(al.kinds, ["watchlist_link", "dossier_request", "dossier_invoice"]) && same(al.events, ["cta_click", "cta_click", "cta_click"]);
    if (input.clearanceProtocol) {
      const cl = ctaClicks(input.clearanceProtocol, "/protocols/" + input.clearanceSlug + "/");
      res.b_cta_clearance_protocol = same(cl.kinds, ["watchlist_link", "reverify_request", "scan_free", "free_notify", "clearance", "clearance_invoice"])
        && same(cl.events, ["cta_click", "cta_click", "cta_click", "cta_click", "cta_click", "cta_click"]);
    }
    if (input.brief) {
      const br = ctaClicks(input.brief, "/briefs/" + input.briefSlug + "/");
      res.b_cta_clearance_brief = same(br.kinds, ["free_notify", "clearance", "clearance_invoice"]) && same(br.events, ["cta_click", "cta_click", "cta_click"]);
    }
    const hp = ctaClicks(input.index, "/");
    res.b_cta_pricing = same(hp.kinds, ["pricing_free", "pricing_mcp", "pricing_scan_9", "pricing_watch_free", "pricing_reverify",
                                        "pricing_x402_verdict", "pricing_x402_dossier", "pricing_x402_wallet_exposure", "pricing_x402_calldata_sim", "pricing_x402_deep_scan",
                                        "pricing_clearance", "pricing_community", "pricing_api_sla"])
      && hp.events.length === 13 && hp.events.every((e) => e === "cta_click");
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
  // Monday sponsor week (task-7a0c85171417): wk_20YYMMDD passes the 5-digit rule (only that exact shape), medium=sponsor is kept,
  // and the landing campaign also rides on live_checker_submit (not only page_load)
  const wk = run(input.index, null, { path: "/", beacon: B, search: "?utm_source=x402list&utm_medium=sponsor&utm_campaign=wk_20261123" });
  if (typeof wk.window.pactaBeacon === "function") wk.window.pactaBeacon("live_checker_submit", "ethereum:0x" + "ab".repeat(20));
  const wkEv = wk.events(), wkLoad = wkEv.find((e) => e.e === "page_load"), wkLive = wkEv.find((e) => e.e === "live_checker_submit");
  res.b_sponsor_week = !!wkLoad && wkLoad.c === "wk_20261123" && wkLoad.m === "sponsor" && !!wkLive && wkLive.c === "wk_20261123"
    && ["wk_2026112", "wk_202611234", "wk_19261123", "xwk_20261123", "wk_20261123_12345"].every((c) => !("c" in ev0({ search: "?utm_campaign=" + c })));
  res.b_v5_host = ev0({ hostname: "pacta.fractalneurons.com" }).h === "com" && ev0({ hostname: "pacta.fractalneurons.com", referrer: "https://pacta.fractalneurons.com/" }).r === "self"
    && ev0({}).h === "wtf" && ev0({ hostname: "pacta-fractalneurons.pages.dev" }).h === "wtf"
    && run(input.index, null, { path: "/website-test/scan/", hostname: "pacta.dri.network", beacon: B }).beacons.length === 0
    && run(input.index, null, { path: "/", hostname: "localhost", beacon: B }).beacons.length === 0
    && run(input.index, null, { path: "/", hostname: "127.0.0.1", beacon: B }).beacons.length === 0;
  res.b_v5_rescued_sends_nothing = run(input.index, null, { path: "/", beacon: B, win: { pactaRescued: 1 } }).beacons.length === 0;
  // /watch/ is a first-class route (page_load p=/watch/ on both production hosts, i: 1 on ?internal=1, nothing under DNT); deeper paths stay /other
  if (input.watch) {
    const wEv = (o) => run(input.watch, null, Object.assign({ path: "/watch/", beacon: B }, o)).events();
    res.b_watch_route = same(wEv({}), [{ v: 1, e: "page_load", p: "/watch/", h: "wtf" }])
      && same(wEv({ hostname: "pacta.fractalneurons.com" }), [{ v: 1, e: "page_load", p: "/watch/", h: "com" }])
      && wEv({ path: "/watch/index.html" })[0].p === "/watch/" && wEv({ path: "/watch" })[0].p === "/watch/"
      && same(wEv({ search: "?internal=1" }), [{ v: 1, e: "page_load", p: "/watch/", i: 1, h: "wtf" }])
      && wEv({ nav: { doNotTrack: "1" } }).length === 0
      && wEv({ path: "/watch/x" })[0].p === "/other" && wEv({ path: "/watchlist/" })[0].p === "/other";
  } else res.b_watch_route = false;
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
  const LIVE = "https://api.pacta.wtf/v1/briefs/live-timelocks?caller_agent=pacta-wtf-radar&requester_role=individual_user&caller_purpose=governance_monitoring";
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
  res.live_static_ready = ids.length === 2 && badge(x.d).textContent === "Window open" && badge(x.d).classList.contains("ready")
    && x.calls.length === 1 && x.calls[0].url === LIVE && x.d.querySelector("[data-live-line]").textContent === "";
  // live: both executed -> EXECUTED, banner flips, clause says superseded, latest block named
  x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", { status: 200, body: { operations: ids.map((i) => op(i, { status: "done", isOperationDone: true, isOperationPending: false })) } });
  const ban = x.d.getElementById("post-eta-status");
  res.live_flips_executed = badge(x.d).textContent === "Executed" && badge(x.d).classList.contains("executed") && !badge(x.d).classList.contains("ready")
    && ban.classList.contains("executed") && /live re-check at block #26,420,000: Executed/.test(ban.querySelector(".ps-clause").textContent)
    && /#26,420,000/.test(x.d.querySelector("[data-live-line]").textContent);
  // live: one ready, one done -> MIXED; still ready -> READY (no change of meaning)
  x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", { status: 200, body: { operations: [op(ids[0], { status: "ready", isOperationPending: true, isOperationDone: false }), op(ids[1], { status: "done", isOperationDone: true })] } });
  res.live_mixed = badge(x.d).textContent === "Mixed" && badge(x.d).classList.contains("mixed");
  x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", { status: 200, body: { operations: ids.map((i) => op(i, { status: "ready", isOperationPending: true, isOperationDone: false })) } });
  res.live_ready_kept = badge(x.d).textContent === "Window open" && badge(x.d).getAttribute("data-live") === "1";
  // failures keep the static state: HTTP 502, malformed JSON, missing / partial operations, markup in the payload stays text
  let keep = true;
  for (const reply of [{ status: 502, body: {} }, { status: 200, bad: true }, { status: 200, body: { operations: "nope" } },
    { status: 200, body: { operations: [op(ids[0], { status: "done", isOperationDone: true })] } },
    { status: 200, body: { operations: ids.map((i) => op(i, { status: "<img src=x onerror=alert(1)>" })) } }]) {
    x = await runWith(input.timelockBrief, "/briefs/ethena-ops-0x0ca0-0x1fe5/", reply);
    keep = keep && badge(x.d).textContent === "Window open" && !x.d.querySelectorAll("img").some((i) => i.getAttribute("onerror") !== null);
  }
  res.live_failures_keep_static = keep;
  // homepage #radar (the active queue): an active row's badge updates; pages without data-live-timelocks never fetch
  const hb = run(input.index, input.app, { path: "/", fetch: () => Promise.reject(new Error("offline")) }).document.querySelectorAll("#radar [data-ops]")[0];
  const hids = hb ? (hb.getAttribute("data-ops") || "").split(/\s+/).filter(Boolean) : [];
  x = await runWith(input.index, "/", { status: 200, body: { operations: hids.map((i) => op(i, { status: "done", isOperationDone: true })) } });
  const row = hids.length ? x.d.querySelectorAll("#radar [data-ops]").find((b) => b.getAttribute("data-ops") === hids.join(" ")) : null;
  res.live_radar_row = !!row && row.textContent === "Executed" && x.calls.filter((c) => /live-timelocks/.test(c.url)).length === 1
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
// (j2) T1 late-payload race (v4.1; Business Point 3: the guard is 18 s, never "failed"): once the fallback has shown the pinned snapshot, a live response that resolves afterwards
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
    const guard = timers.find((t) => t.ms === 18000);
    if (!guard || timers.some((t) => t.ms === 9000)) return { ok: false, why: "no 18000 ms guard (or a 9000 ms one)" };
    guard.fn();
    const recheck = d.querySelector("[data-last-recheck]"), recheckTxt = recheck ? recheck.textContent : "";
    const afterGuard = snap();
    const fallbackShown = /Live check unavailable: showing the pinned snapshot/.test(afterGuard) && !d.querySelector("[data-live-pending]");
    const payload = { operations: badges().flatMap((b) => (b.getAttribute("data-ops") || "").split(/\s+/).filter(Boolean))
      .map((id) => ({ opId: id, live: { status: "pending", isOperationPending: true, isOperationDone: false }, block: { number: 26999999 } })) };
    if (lateBody) releaseJson(payload); else { releaseFetch.payload = payload; releaseFetch(); }
    for (let i = 0; i < 6; i++) await flush();
    return { ok: pendingBefore && fallbackShown && !/failed/i.test(recheckTxt)
      && (!recheck || recheckTxt === "Showing pinned snapshot") && snap() === afterGuard && !!signals[0] && signals[0].aborted === true
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
  // v4: one vocabulary (M3) and the scorecard counts (M4): Deltas / Protective / Aligned / Observed, labels "(n)"
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
    && d.getElementById("proto-active").textContent.includes("Docs vs chain: Deltas") && d.getElementById("proto-active").textContent.includes("Chain: Base") && !clear.hidden;
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
  // v6 E16: the live receipt leads with Usual Money's settled weaker-protection finding
  const instant = !!pc && pcv("[data-pc-name]") === "Usual Money (USD0 / USD0++)" && pcv("[data-pc-docs]") === "DEFAULT_ADMIN handover waits three days"
    && pcv("[data-pc-chain]") === "DEFAULT_ADMIN handover delay: one second (defaultAdminDelay() = 1s)"
    && /^Ethereum #[\d,]+$/.test(pcv("[data-pc-block]")) && pc.querySelector("[data-pc-href]").getAttribute("href") === "protocols/usual-money-usd0-usd0/"
    && go.getAttribute("aria-pressed") === "true";
  await flush(); await flush(); await flush();
  const t = out.textContent, link = out.querySelectorAll("a").find((a) => a.textContent === "Full record");
  res.v_hero_receipts = rec.length === 4 && instant && rec.every((b) => /^0x[0-9a-fA-F]{40}$/.test(b.getAttribute("data-pf-address") || ""))
    && rec.map((b) => b.getAttribute("data-r-name")).join("|") === "Usual Money (USD0 / USD0++)|Treehouse (TREE)|Moonwell (Base)|Ethena (USDe / sUSDe)";
  res.v_hero_click_fetches = calls.length === 1 && calls[0].includes("address=" + go.getAttribute("data-pf-address"));
  res.v_assessment_next_to_score = !t.includes("Heuristic score") && !t.includes("/100") && t.includes("Confidence medium") && t.includes("Indexed & verified record")
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
  res.v_ages = ages.length >= 1 && ages.every((a) => / \(\d+d \d+h \d+m ago\)$| \(\d+h \d+m ago\)$/.test(a.textContent));
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
  // "1 window open · 1 waiting · Executed (2 ops)", so the line never reads as a total
  const OPS = "( \\(\\d+ ops?\\))?", PART = "(\\d+ (window open|waiting|mixed|cancelled or unknown)" + OPS + "|Executed \\(\\d+ ops?\\))";
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
    && !out.textContent.includes("/100") && !!out.querySelector("[data-pf-scope]") && !out.textContent.includes("cannot be changed");
  // NO_CONTROLLER_FOUND (Worker 6c78f406): neutral, "No controller found by our checks", riskScore null, the checks run listed
  await submit({ ...PF_EXAMPLE, verdict: "NO_CONTROLLER_FOUND", riskScore: null, isProxy: false, implementation: null, hasAdminSlot: false,
    controller: { address: null, kind: "none" }, capabilities: {}, assessment: { confidence: "low", coverage: "unindexed_bytecode_heuristic" },
    summary: "No controller found by our checks (see checksRun); custom or unprobed control paths may still exist.",
    checksRun: ["eth_getCode(target)", "EIP-1967 implementation slot", "owner()", "upgradeAdmin()", "committee()"] });
  const nt = out.querySelector(".pf-verdict"), nb = out.querySelector("[data-pf-badge]"), nc = out.querySelector("[data-pf-checks]");
  res.ncf_verdict_checks_run = !!nt && nt.textContent === "No controller found by our checks" && !!nb && nb.getAttribute("data-variant") === "neutral"
    && !!nc && nc.getAttribute("data-pf-checks") === "5" && nc.textContent.includes("Checks run (5)") && nc.textContent.includes("committee()")
    && out.textContent.includes("custom or unprobed control paths may still exist") && out.textContent.includes("low")
    && !out.textContent.includes("/100") && !/immutable/i.test(out.textContent)
    && !out.querySelectorAll(".pf-dl dd, .pf-metrics dd").some((dd) => dd.textContent === "null");   // the raw JSON drawer may show null fields
  // legacy: IMMUTABLE_NO_ADMIN (verified-source records only) still renders its own headline (pp3_immutable_headline above)
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
    // a Base chip (Moonwell) then an Ethereum chip (Usual Money): chain switching and one live check per click
    const chips = d.querySelectorAll("[data-receipt]"), yo = chips.find((b) => b.getAttribute("data-r-name") === "Moonwell (Base)");
    const stader = chips.find((b) => b.getAttribute("data-r-name") === "Usual Money (USD0 / USD0++)");
    calls.length = 0;
    addr.value = "0x123"; form.dispatchEvent(new Event_("submit")); await flush();
    const errShown = addr.getAttribute("aria-invalid") === "true" && err.hidden === false && calls.length === 0;
    yo.dispatchEvent(new Event_("click")); await flush(); await flush(); await flush();
    const box = form.parentNode, kids = box.children;
    const yoOk = errShown && sel.value === "base" && addr.value === yo.getAttribute("data-pf-address") && addr.getAttribute("aria-invalid") === null
      && err.hidden === true && err.textContent === "" && calls.length === 1
      && calls[0].includes("chain=base&address=" + yo.getAttribute("data-pf-address"))
      && !!out.querySelector("[data-pf-result]") && !out.textContent.includes("/100") && out.textContent.includes("MULTISIG_NO_TIMELOCK")
      && out.parentNode === box && kids.indexOf(form) >= 0 && kids.indexOf(form) < kids.indexOf(out)
      && d.querySelector("[data-pc-name]").textContent === "Moonwell (Base)" && yo.getAttribute("aria-pressed") === "true";
    stader.dispatchEvent(new Event_("click")); await flush(); await flush(); await flush();
    const staderOk = sel.value === "ethereum" && addr.value === stader.getAttribute("data-pf-address") && calls.length === 2
      && calls[1].includes("chain=ethereum&address=" + stader.getAttribute("data-pf-address")) && !!out.querySelector("[data-pf-result]")
      && d.querySelector("[data-pc-name]").textContent === "Usual Money (USD0 / USD0++)" && stader.getAttribute("aria-pressed") === "true"
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
    && /claude mcp add --transport http pacta https:\/\/(?:api\.pacta\.wtf|pacta\.fractalneurons\.com|pacta-x402\.pacta\.workers\.dev)\/mcp/.test(pAg.textContent) && /cast call /.test(pAg.textContent)
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
    && out.stable_rwa.n === 70 && out.eth_lst_lrt.n === 46 && out.lending_vaults.n === 124 && out.base.n === 37
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
  res.v44_radar_live_pill = !!pill && pill.textContent === "Live-checked · #26,999,999" && !asof;   // "Next:" never repeats the snapshot time
  const p0pill = p0.document.querySelector("#radar [data-prov-pill]"), p0asof = p0.document.querySelector("#radar .livebar .lb-asof");
  res.v44_radar_pill_stays_pinned_offline = !!p0pill && /^Scanner-pinned \(L1( \+ Base)? finalized\)$/.test(p0pill.textContent) && !p0asof;
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
  const chip = d.querySelectorAll("[data-receipt]").find((b) => b.getAttribute("data-r-name") === "Usual Money (USD0 / USD0++)");
  chip.dispatchEvent(new Event_("click"));
  for (let i = 0; i < 4; i++) await flush();
  const card = out.querySelector("[data-pf-result]"), kids = card ? card.children : [];
  const is = (k, sel) => k.closest(sel) === k, at = (sel) => kids.findIndex((k) => is(k, sel));
  const iVerdict = at(".pf-verdict-row"), iMetrics = at(".pf-metrics"), iMatch = at("[data-pf-match]"), iScope = at("[data-pf-scope]");
  const lim = card ? card.querySelector("details[data-pf-limits]") : null;
  const visibleText = card ? kids.filter((k) => !is(k, '[data-slot="accordion"]') && !is(k, ".live-verify")).map((k) => k.textContent).join(" ") : "";
  const dvc = card ? card.querySelector("[data-pf-dvc]") : null, scope = card ? card.querySelector("[data-pf-scope]") : null;
  res.v44_live_card_verdict_first = !!card && iVerdict === 1 && iMetrics === iVerdict + 1 && iMatch === iMetrics + 1 && iScope === iMatch + 1
    && !!dvc && dvc.textContent === "Docs vs chain: Delta" && dvc.getAttribute("data-variant") === "warning"
    && scope.textContent === "The verdict covers only this one contract address (" + reply.address.slice(0, 6) + "…"
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
// P3-CONTACT-03 on /request/: with contact_handle, "Request received" only when the answer says it was stored; a 200 without the
// flags (live 069b6222 with a failed private store), a "NOT stored" note or a 503 keeps the form, the entries and the plain line.
// Without a contact (an anonymous vote) a 200 still shows the receipt, as before, even when the Worker has no store (persisted:false).
async function requestNotStoredScenario() {
  const NOT_SAVED = "We could not confirm whether your submission was saved. Your entries are still here \u2014 please try again, or write to pacta@dri.network.";   // NOT_SAVED_TXT: "could not confirm", never "not saved"
  const R = { schema: "pacta.demand_receipt.v1", request_id: "REQ-2026-0a1b2c3d", status: "queued", demand_votes: 1, fast_track_url: "https://pacta.wtf/request/?tier=clearance" };
  const NS = "The contact handle was NOT stored (no private store available); nothing was published.";
  const cases = [
    ["contact:persisted_false", "risk.desk@fund-ops.co", 200, { ...R, has_contact_opt_in: false, persisted: false, note: NS }, false],
    ["contact:opt_in_false", "risk.desk@fund-ops.co", 200, { ...R, has_contact_opt_in: false, persisted: true }, false],
    ["contact:note_not_stored", "@pacta_ops", 200, { ...R, status: "upvoted_existing", has_contact_opt_in: true, persisted: true, note: NS }, false],
    ["contact:503", "octocat", 503, { error: "contact_storage_unavailable", detail: "We could not confirm whether your submission was saved. Please try again, or write to pacta@dri.network" }, false],
    ["contact:stored", "risk.desk@fund-ops.co", 200, { ...R, has_contact_opt_in: true, persisted: true, note: "The contact handle was stored privately (never published) for follow-up." }, true],
    ["anonymous:no_store", "", 200, { ...R, has_contact_opt_in: false, persisted: false, note: "Queued in Pacta's public demand queue." }, true],
  ];
  const out = {};
  for (const [name, contact, st0, body0, ok] of cases) {
    const calls = [];
    const p = run(input.request, input.app, { path: "/request/", fetch: (url, o) => { calls.push([String(url), o]); return Promise.resolve({ status: st0, ok: st0 >= 200 && st0 < 300, json: () => Promise.resolve(body0) }); } });
    for (let i = 0; i < 3; i++) await flush();
    const d = p.document, form = d.getElementById("req-form"), done = d.getElementById("req-done"), st = d.getElementById("req-status"), send = d.getElementById("req-send");
    setField(d, "req-org", "Harness Risk Desk"); setField(d, "req-contact", contact);
    const before = ["req-org", "req-contact"].map((id) => d.getElementById(id).value).join("|");
    const ev = new Event_("submit"); ev.target = form; form.dispatchEvent(ev);
    for (let i = 0; i < 6; i++) await flush();
    const sent = calls.length === 1 ? JSON.parse(calls[0][1].body) : {};
    const bodyOk = calls.length === 1 && calls[0][0] === "https://api.pacta.wtf/v1/requests" && (contact ? sent.contact_handle === contact : !("contact_handle" in sent));
    out[name] = ok
      ? bodyOk && form.hidden === true && done.hidden === false && d.querySelector("[data-req-done-title]").textContent === "Request received"
      : bodyOk && form.hidden !== true && done.hidden === true && st.textContent === NOT_SAVED && send.disabled === false
        && ["req-org", "req-contact"].map((id) => d.getElementById(id).value).join("|") === before;
  }
  res.req_not_stored_results = out;
  res.req_not_stored_keeps_form = Object.keys(out).length === 6 && Object.values(out).every(Boolean);
}

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
    && !!out.querySelector("[data-pf-dvc]") && out.querySelector("[data-pf-dvc]").textContent === "Docs vs chain: Delta";
  const ml = out.querySelectorAll("details[data-pf-limits] a").find((a) => a.textContent === "How the heuristic score differs from Docs vs chain");
  res.v45_live_checker_link = !!ml && ml.getAttribute("href") === "https://pacta.wtf/methodology/#live-checker"
    && !out.textContent.includes("/100") && !out.textContent.includes("Risk score");
}

// (q) Option B v2: one product per page (/scan/, /webhook/, /seal/): exact amount + EIP-681 link, ONE primary action (a browser-wallet
//     transfer, or the manual drawer without a wallet), the order frozen at Pay, every control locked in flight, the API's order codes
async function checkoutScenario() {
  const C = input.checkout;
  if (!C || !input.scan || !input.watch || !input.seal) { res.co_error = "no checkout input"; return; }
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
    return f.getAttribute("data-sku") === sku && d.querySelectorAll('input[name="sku"]').length === 0
      && d.querySelector("[data-co-amount]").textContent === C.amounts[sku] + " USDC"
      && d.querySelector("[data-co-eip681]").getAttribute("href") === eip(C.skus[sku])
      && d.getElementById("co-wallet").hidden === false && !m.hasAttribute("open") && d.getElementById("co-result").hidden === true;
  };
  const webDoc = page(input.watch, "/watch/").document;   // /watch/ sells nothing: no checkout form, no pay button, no wallet
  res.co_single_sku_pages = shape(page(input.scan, "/scan/").document, "wallet-report-9")
    && !page(input.seal, "/seal/").document.getElementById("co-form") && page(input.seal, "/seal/").document.querySelectorAll("a").some((a_) => (a_.getAttribute("href") || "").includes("request/?tier=clearance"))
    && !webDoc.getElementById("co-form") && !webDoc.querySelector("[data-co-pay]") && !!webDoc.getElementById("watch-form") && !!webDoc.getElementById("pledge-form");
  // no browser wallet: the primary action checks the order first, then opens the manual transfer drawer (never a dead button)
  calls = [];
  let p = page(input.scan, "/scan/", { fetch: okFetch(200, {}) }), d = p.document;
  click(d.getElementById("co-wallet"));
  const blocked = !d.getElementById("co-manual").hasAttribute("open") && d.getElementById("co-target-err").hidden === false;
  setv(d, "pf-address", ADDR); click(d.getElementById("co-wallet"));
  res.co_no_wallet_opens_drawer = blocked && d.getElementById("co-manual").hasAttribute("open")
    && /No browser wallet/.test(d.getElementById("co-status").textContent) && calls.length === 0;
  // /scan/: an example chip fills the scanner and runs the free live check; the order then uses that target
  calls = [];
  p = page(input.scan, "/scan/", { fetch: okFetch(200, { order_id: "ord_chip" }) }); d = p.document;
  const chip = d.querySelectorAll("[data-receipt]")[0], chipAddr = chip.getAttribute("data-pf-address");
  click(chip); await flush(); await flush();
  const pfCall = calls.find((c) => /\/v1\/check\/preflight\?/.test(String(c[0])));
  setv(d, "co-tx", TXH); submit(d); await flush(); await flush();
  const post = calls.find((c) => c[0] === C.api);
  res.co_scan_chip_previews_and_orders = d.getElementById("pf-address").value === chipAddr && !!pfCall && String(pfCall[0]).includes(chipAddr)
    && !!post && JSON.parse(post[1].body).target_address === chipAddr && JSON.parse(post[1].body).sku === "wallet-report-9";
  // the exact contract body; the result is text only
  calls = [];
  const okBody = { order_id: "ord_harness_1", status: "verified <img src=x onerror=alert(1)>", report: { proxy_admin: "0x" + "ef".repeat(20) } };
  p = page(input.scan, "/scan/", { fetch: okFetch(200, okBody) }); d = p.document;
  setv(d, "pf-chain", "base"); setv(d, "pf-address", ADDR); setv(d, "co-docs", "https://docs.example.invalid"); setv(d, "co-contact", "@harness"); setv(d, "co-tx", TXH);
  submit(d); await flush(); await flush();
  const b0 = calls[0] ? JSON.parse(calls[0][1].body) : null;
  res.co_verify_posts_exact_body = calls.length === 1 && calls[0][0] === C.api && calls[0][1].method === "POST"
    && same(b0, { sku: "wallet-report-9", tx_hash: TXH, chain: "base", target_chain: "base", target_address: ADDR, protocol_or_docs: "https://docs.example.invalid", webhook_or_contact: "@harness" });
  const out = d.getElementById("co-result"), payA = out.querySelector("[data-co-r-pay] a");
  res.co_result_text_only = out.hidden === false && d.querySelector("[data-co-r-order]").textContent === "ord_harness_1"
    && d.querySelector("[data-co-r-status]").textContent.includes("<img src=x") && out.querySelectorAll("img").length === 0
    && d.getElementById("co-json").textContent.includes('"proxy_admin"') && !!payA && payA.getAttribute("href") === "https://basescan.org/tx/" + TXH;
  // the Worker's order codes: poll codes keep the order locked and waiting; final codes unlock with a specific message
  const codeRun = async (status, error) => {
    calls = [];
    const q = page(input.scan, "/scan/", { fetch: okFetch(status, error === null ? "Not Found" : { error }) }), qd = q.document;
    setv(qd, "pf-address", ADDR); setv(qd, "co-tx", TXH); submit(qd); await flush(); await flush();
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
  p = page(input.scan, "/scan/", { fetch: () => Promise.reject(new Error("offline")) }); d = p.document;
  setv(d, "pf-address", ADDR); setv(d, "co-tx", TXH); submit(d); await flush(); await flush();
  res.co_errors_reported = /Could not reach the verifier/.test(d.getElementById("co-status").textContent) && d.getElementById("co-result").hidden === true;
  // wallet (/seal/): switch to Base, ONE eth_sendTransaction = USDC.transfer(treasury, exact amount), then the frozen order is verified
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
  p = page(input.scan, "/scan/", { win: { ethereum: eth }, fetch: okFetch(200, { order_id: "ord_w" }) }); d = p.document;
  setv(d, "pf-address", ADDR); setv(d, "co-contact", "@team"); click(d.getElementById("co-wallet"));
  for (let i = 0; i < 8; i++) await flush();
  const send = wcalls.find((a) => a.method === "eth_sendTransaction");
  const want = "0xa9059cbb" + pad(C.treasury.slice(2).toLowerCase()) + pad(C.skus["wallet-report-9"].toString(16));
  const body1 = calls[0] ? JSON.parse(calls[0][1].body) : {};
  res.co_wallet_transfer_only = wcalls.some((a) => a.method === "wallet_switchEthereumChain" && a.params[0].chainId === "0x2105")
    && !!send && same(send.params, [{ from: "0x" + "ab".repeat(20), to: C.usdc, value: "0x0", data: want }])
    && wcalls.filter((a) => a.method === "eth_sendTransaction").length === 1 && !wcalls.some((a) => /approve|allowance|sign/i.test(a.method))
    && d.getElementById("co-tx").value === TXH && calls.length === 1 && body1.tx_hash === TXH && body1.sku === "wallet-report-9"
    && body1.webhook_or_contact === "@team";
  const eth2 = { request: (a) => a.method === "eth_sendTransaction" ? Promise.reject(Object.assign(new Error("denied"), { code: 4001 })) : eth.request(a) };
  chain = "0x2105"; calls = [];
  p = page(input.scan, "/scan/", { win: { ethereum: eth2 }, fetch: okFetch(200, {}) }); d = p.document;
  setv(d, "pf-address", ADDR); click(d.getElementById("co-wallet")); for (let i = 0; i < 8; i++) await flush();
  res.co_wallet_cancel_sends_nothing = calls.filter((c) => c[0] === C.api).length === 0 && /Cancelled in the wallet/.test(d.getElementById("co-status").textContent)
    && d.getElementById("co-wallet").disabled === false && d.getElementById("pf-address").disabled === false;
  // one payment at a time, and the order frozen at Pay: while the prompt is open every control is locked (the scanner, the chips and
  // the order fields too); a forced change during the prompt never reaches the POST; everything unlocks once it settles
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
  p = page(input.scan, "/scan/", { win: { ethereum: eth3 }, fetch: okFetch(200, { order_id: "ord_once" }) }); d = p.document;
  setv(d, "pf-address", ADDR); setv(d, "co-docs", "https://docs.example.invalid/a"); setv(d, "co-contact", "@harness");
  const w3 = d.getElementById("co-wallet");
  click(w3); await flush(); click(w3); click(w3); await flush();
  const ids3 = ["co-wallet", "co-verify", "pf-address", "pf-chain", "pf-submit", "co-docs", "co-contact", "co-tx"];
  const locked3 = ids3.every((id) => d.getElementById(id).disabled === true) && d.querySelectorAll("[data-receipt]").every((b) => b.disabled === true);
  setv(d, "pf-address", "0x" + "99".repeat(20)); setv(d, "co-docs", "https://evil.example.invalid"); setv(d, "co-contact", "@other");
  setv(d, "co-tx", TXH); submit(d); await flush();
  const noVerifyDuring = calls.filter((c) => c[0] === C.api).length === 0;
  release(); for (let i = 0; i < 8; i++) await flush();
  const posts3 = calls.filter((c) => c[0] === C.api), b3 = posts3[0] ? JSON.parse(posts3[0][1].body) : {};
  res.co_wallet_single_flight = locked3 && noVerifyDuring && wc3.filter((m) => m === "eth_requestAccounts").length === 1
    && wc3.filter((m) => m === "eth_sendTransaction").length === 1 && posts3.length === 1
    && ids3.every((id) => d.getElementById(id).disabled === false) && d.getElementById("co-result").hidden === false;
  res.co_snapshot_and_inputs_locked = locked3 && posts3.length === 1
    && same(b3, { sku: "wallet-report-9", tx_hash: TXH, chain: "base", target_chain: "ethereum", target_address: ADDR, protocol_or_docs: "https://docs.example.invalid/a", webhook_or_contact: "@harness" });
  // /seal/?protocol=<slug> (the protocol pages' seal link): the indexed contract and name come from the public catalog
  const lkFetch = (url) => {
    const u = String(url);
    if (/api\/v1\/lookup\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(input.lookupJson) });
    if (/api\/v1\/scorecards\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(input.scorecardsJson) });
    return Promise.reject(new Error("not needed"));
  };
  p = page(input.seal, "/seal/", { search: "?protocol=stader-labs-ethx", fetch: lkFetch }); d = p.document;
  for (let i = 0; i < 4; i++) await flush();
  const stx = input.lookupJson.items.find((i) => i.slug === "stader-labs-ethx");
  // Section 7: /seal/ sells nothing; it explains re-verification by arrangement and links /request/ (no checkout fields to prefill)
  res.co_seal_protocol_prefill = !!stx && !d.getElementById("co-form") && d.querySelectorAll("a").some((a_) => (a_.getAttribute("href") || "").includes("request/?tier=clearance"));
  // /request/?tier=seal-99 forwards to the seal page (keeping the protocol); an enterprise tier stays on /request/
  const lr = run(input.request, input.app, { path: "/request/", search: "?tier=seal-99&protocol=stader-labs-ethx" });
  const lr2 = run(input.request, input.app, { path: "/request/", search: "?tier=clearance" });
  res.co_request_launcher_forward = lr.location.replaced === "../seal/?protocol=stader-labs-ethx" && !lr2.location.replaced
    && lr.document.querySelectorAll("[data-launcher] a").length === 3;
  // Mobile WebView 1-tap wallet deep-links (/scan/ and /seal/): shown ONLY when !window.ethereum and mobile UA;
  // strips staging /website-test prefix from target pacta.wtf dApp URL, preserves ?chain=...&address=..., syncs edits, and fires cta_click
  const mobileUa = "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.0.0 Mobile Safari/537.36";
  const scanStage = JSON.parse(JSON.stringify(input.scan));
  scanStage[1]["data-base-path"] = "/website-test";
  const qsInit = "?chain=base&address=" + C.usdc;
  const mwScan = run(scanStage, input.app, { path: "/website-test/scan/", search: qsInit, nav: { userAgent: mobileUa }, beacon: input.beacon });
  const mwDoc = mwScan.document, dlScan = mwDoc.getElementById("co-deeplinks");
  const mmA = mwDoc.querySelector("[data-co-metamask]"), cbA = mwDoc.querySelector("[data-co-coinbase]");
  const wantCanon = "/scan/" + qsInit;
  const scanInitOk = !!dlScan && dlScan.hidden === false && mwDoc.getElementById("co-form").getAttribute("data-mobile-webview") === "true"
    && mwDoc.getElementById("pf-chain").value === "base" && mwDoc.getElementById("pf-address").value === C.usdc
    && mmA.getAttribute("href") === "https://metamask.app.link/dapp/pacta.wtf" + wantCanon
    && cbA.getAttribute("href") === "https://go.cb-wallet.com/dapp?cb_url=" + encodeURIComponent("https://pacta.wtf" + wantCanon)
    && !mwDoc.getElementById("co-manual").hasAttribute("open");
  const bBefore = mwScan.beacons.length;
  click(mmA); click(cbA);
  const ctaEvents = mwScan.events().slice(bBefore).map((e) => e.e);
  setField(mwDoc, "pf-address", ADDR);
  const wantEdited = "/scan/?chain=base&address=" + ADDR;
  const scanEditOk = mmA.getAttribute("href") === "https://metamask.app.link/dapp/pacta.wtf" + wantEdited
    && cbA.getAttribute("href") === "https://go.cb-wallet.com/dapp?cb_url=" + encodeURIComponent("https://pacta.wtf" + wantEdited);
  const sealStage = JSON.parse(JSON.stringify(input.seal));
  sealStage[1]["data-base-path"] = "/website-test";
  const mwSeal = run(sealStage, input.app, { path: "/website-test/seal/", search: "?chain=ethereum&address=" + ADDR, nav: { userAgent: mobileUa } });
  const sealOk = !mwSeal.document.getElementById("co-deeplinks");   // Section 7: /seal/ has no wallet checkout
  // Desktop without wallet OR mobile inside MetaMask/Coinbase (window.ethereum present): deep-link block stays hidden
  const deskScan = run(input.scan, input.app, { path: "/scan/", nav: { userAgent: "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36" } });
  const injectedMobile = run(input.scan, input.app, { path: "/scan/", search: qsInit, nav: { userAgent: mobileUa }, win: { ethereum: eth } });
  res.co_mobile_webview_deeplinks = scanInitOk && scanEditOk && sealOk && same(ctaEvents, ["cta_click", "cta_click"])
    && deskScan.document.getElementById("co-deeplinks").hidden === true
    && injectedMobile.document.getElementById("co-deeplinks").hidden === true
    && injectedMobile.document.getElementById("pf-address").value === C.usdc;

  // Progressive cold-traffic funnel on /scan/: cold load hides #scan-upgrade & #co-card; running a free check reveals #scan-upgrade
  // and syncs target + /seal/ link; clicking #scan-open-co expands #co-card; ?unlock=1 opens both immediately.
  const pfOkFetch = (url) => Promise.resolve({
    status: 200, ok: true,
    json: () => Promise.resolve({ verdict: "ZERO_DELAY_ADMIN_UPGRADE", chain: "base", address: C.usdc, pinnedBlock: 22000000, riskScore: 65 })
  });
  const coldScan = page(input.scan, "/scan/", { search: "?utm_source=x&utm_medium=paid", fetch: pfOkFetch }), cd = coldScan.document;
  const coldHidden = cd.getElementById("scan-upgrade").hidden === true && cd.getElementById("co-card").hidden === true;
  const usdcChip = cd.querySelectorAll("[data-receipt]").find((b) => b.getAttribute("data-pf-address") === C.usdc) || cd.querySelectorAll("[data-receipt]")[0];
  const chipA = usdcChip.getAttribute("data-pf-address"), chipCh = usdcChip.getAttribute("data-pf-chain");
  click(usdcChip); for (let i = 0; i < 5; i++) await flush();
  const revealedAfterCheck = cd.getElementById("scan-upgrade").hidden === false && cd.getElementById("co-card").hidden === true
    && cd.getElementById("co-sync-pill").textContent.includes(chipA.slice(0, 6))
    && cd.getElementById("scan-to-seal").getAttribute("href") === "../request/?tier=clearance&chain=" + chipCh + "&address=" + chipA;
  click(cd.getElementById("scan-open-co"));
  const openedCo = cd.getElementById("co-card").hidden === false && cd.getElementById("scan-open-co").getAttribute("aria-expanded") === "true";
  const manualScan = page(input.scan, "/scan/"); click(manualScan.document.getElementById("scan-reveal-btn"));
  const manualRevOk = manualScan.document.getElementById("scan-upgrade").hidden === false;
  const directUnlock = page(input.scan, "/scan/", { search: "?unlock=1" });
  const unlockParamOk = directUnlock.document.getElementById("scan-upgrade").hidden === false && directUnlock.document.getElementById("co-card").hidden === false;
  res.co_progressive_scan_funnel = coldHidden && revealedAfterCheck && openedCo && manualRevOk && unlockParamOk;
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

  const ctaWallet = run(input.scan, input.app, { path: "/scan/", hostname: "127.0.0.1" });   // Section 7: /scan/ is the one wallet checkout
  click(ctaWallet.document.getElementById("co-wallet"));
  click(ctaWallet.document.getElementById("co-wallet"));
  const walletLeadOnce = same(ctaWallet.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  const ctaDl = run(input.scan, input.app, { path: "/scan/", hostname: "127.0.0.1", nav: { userAgent: mobileUa } });
  click(ctaDl.document.querySelector("[data-co-metamask]"));
  click(ctaDl.document.querySelector("[data-co-coinbase]"));
  const dlLeadOnce = same(ctaDl.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  const ctaDrawer = run(input.scan, input.app, { path: "/scan/", hostname: "127.0.0.1" });
  click(ctaDrawer.document.querySelector("#co-manual summary"));
  click(ctaDrawer.document.querySelector("#co-manual summary"));
  const drawerLeadOnce = same(ctaDrawer.window.__pactaTwqEvents, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhie", {}]]);

  res.x_pixel_lead_dedup = invalidNoLead && pfLeadOnce && walletLeadOnce && dlLeadOnce && drawerLeadOnce;

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
  const submitScan = async (fetchFn, txHash) => {
    const pg = run(input.scan, input.app, { path: "/scan/", hostname: "127.0.0.1", storage: sharedStorage, fetch: fetchFn });
    pg.document.getElementById("pf-address").value = ADDR;
    pg.document.getElementById("co-tx").value = txHash || TXH;
    pg.document.getElementById("co-form").dispatchEvent(new Event_("submit"));
    await flush(); await flush();
    return pg.window.__pactaTwqEvents;
  };
  const evReal19 = await submitScan(makeVerifyFetch(200, { orderId: "ord_real_19", status: "verified", internalCanary: false }), TXH);
  const evReloadSameOrder = await submitScan(makeVerifyFetch(200, { orderId: "ord_real_19", status: "verified", internalCanary: false }), TXH);
  const evCanary = await submitScan(makeVerifyFetch(200, { orderId: "ord_canary_1", status: "verified", internalCanary: true }), "0x" + "aa".repeat(32));
  const evReplay = await submitScan(makeVerifyFetch(200, { orderId: "ord_replay_1", status: "verified", internalCanary: false }, "true"), "0x" + "bb".repeat(32));

  const evSecond9 = await submitScan(makeVerifyFetch(200, { orderId: "ord_real_9b", status: "verified", internalCanary: false }), "0x" + "cc".repeat(32));

  res.x_pixel_purchase_rules = same(evReal19, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhif", { value: 9, currency: "USD", conversion_id: "ord_real_19" }]])
    && same(evReloadSameOrder, [["config", "rjbqn"]])
    && same(evCanary, [["config", "rjbqn"]])
    && same(evReplay, [["config", "rjbqn"]])
    && same(evSecond9, [["config", "rjbqn"], ["event", "tw-rjbqn-rjhif", { value: 9, currency: "USD", conversion_id: "ord_real_9b" }]])
    && same(JSON.parse(storeMap["pacta-x-purchased"]), ["ord_real_19", "ord_real_9b"]);
}

async function miniAppScenario() {
  if (!input.miniapp || !input.checkout) { res.ma_error = "no miniapp input"; return; }
  const C = input.checkout;
  const UNIDX = "0x" + "77".repeat(20), TX19 = "0x" + "19".repeat(32), TX99 = "0x" + "99".repeat(32);
  let maOrderPosts = 0;
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
      maOrderPosts++;
      const body = JSON.parse(opts.body);
      const oid = "ord_ma_" + String(body.sku || "");
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

  // 2. Instant Free Check: ALIGNED (USDC preset), DOCUMENTATION DIFFERENCE (Moonwell preset), UNINDEXED (custom 0x...)
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
  const deltaOk = p.document.getElementById("ma-verdict").getAttribute("data-ma-status") === "DOCUMENTATION DIFFERENCE"
    && p.document.getElementById("ma-v-badge").hidden === false;

  p.document.getElementById("ma-address").value = UNIDX;
  p.document.getElementById("ma-check-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 6; i++) await flush();
  const unidxOk = p.document.getElementById("ma-verdict").getAttribute("data-ma-status") === "UNINDEXED"
    && p.document.getElementById("ma-v-badge").hidden === true;

  res.ma_instant_verdicts = alignedOk && deltaOk && unidxOk;

  // 3. Deeper diligence (Part 5): the mini app sells nothing itself; its primary CTA is a plain link to the $9 report on /scan/,
  // the secondary one the by-arrangement request form; clicking either sends no wallet transaction and posts no order
  const upScan = p.document.getElementById("ma-buy-scan"), upSeal = p.document.getElementById("ma-buy-seal");
  const callsBefore = wCalls.length;
  if (upScan) click(upScan);
  if (upSeal) click(upSeal);
  for (let i = 0; i < 6; i++) await flush();
  res.ma_upgrade_link_9 = !!upScan && !!upSeal && upScan.tagName === "A"
    && upScan.getAttribute("href") === "../scan/" && upScan.getAttribute("data-sku") === "wallet-report-9"
    && /Full Wallet (&|&amp;) Safe Exposure Report \(\$9 USDC\)/.test(upScan.textContent)
    && upSeal.tagName === "A" && upSeal.getAttribute("href") === "../request/?tier=clearance"
    && !p.document.getElementById("ma-manual") && !p.document.getElementById("ma-receipt") && !p.document.getElementById("ma-tx")
    && wCalls.slice(callsBefore).length === 0 && maOrderPosts === 0;
}

// CP-03: /miniapp/ resets its result on every new check and on HTTP / network failure (never a previous contract's fields)
async function miniAppResetScenario() {
  if (!input.miniapp) { res.ma_reset_error = "no miniapp input"; return; }
  const A = "0x" + "a1".repeat(20), B = "0x" + "b2".repeat(20), N = "0x" + "c3".repeat(20);
  const mode = {};   // lower-case address -> "ok" | "502" | "reject" | "pending"
  let release = null;
  const okBody = { verdict: "MULTISIG_NO_TIMELOCK", summary: "Block-pinned authority check.", block: { number: 28000555 },
    controller: { kind: "multisig_safe", address: "0x" + "33".repeat(20), safeThreshold: 2, safeOwnerCount: 3 } };
  const fetchFn = (url) => {
    const u = String(url);
    if (/api\/v1\/lookup\.json$/.test(u)) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(input.lookupJson) });
    if (u.includes("/v1/check/preflight")) {
      const m = mode[new URL(u).searchParams.get("address").toLowerCase()] || "ok";
      if (m === "reject") return Promise.reject(new TypeError("Failed to fetch"));
      if (m === "502") return Promise.resolve({ status: 502, ok: false, json: () => Promise.resolve({ error: "upstream_unavailable" }) });
      if (m === "pending") return new Promise((r) => { release = () => r({ status: 200, ok: true, json: () => Promise.resolve(okBody) }); });
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(okBody) });
    }
    return Promise.reject(new Error("unexpected fetch " + u));
  };
  const p = run(input.miniapp, input.app, { path: "/miniapp/", hostname: "127.0.0.1", win: { parent: { postMessage: () => {} } }, fetch: fetchFn });
  for (let i = 0; i < 4; i++) await flush();
  const d = p.document, $ = (id) => d.getElementById(id);
  const eth = d.querySelectorAll("[data-ma-chain]").find((b) => b.getAttribute("data-ma-chain") === "ethereum");
  if (eth) click(eth);
  const sh = (h) => h.slice(0, 6) + "…" + h.slice(-4);
  const submit = async (addr, flushes) => {
    $("ma-address").value = addr; $("ma-check-form").dispatchEvent(new Event_("submit"));
    for (let i = 0; i < (flushes == null ? 6 : flushes); i++) await flush();
  };
  const isReset = (addr, status) => $("ma-verdict").getAttribute("data-ma-status") === status
    && $("ma-v-pill").getAttribute("data-tone") === "unindexed"
    && $("ma-v-pill").textContent === (status === "CHECKING" ? "Checking…" : "Check unavailable")
    && $("ma-v-title").textContent === sh(addr) + " · Ethereum"
    && $("ma-v-badge").hidden === true && !$("ma-v-badge").getAttribute("src")
    && $("ma-v-target").textContent === "ethereum:" + sh(addr)
    && $("ma-v-ctrl").textContent === "—" && $("ma-v-delay").textContent === "—" && $("ma-v-prov").textContent === "—";
  const out = {};
  // 1. the default catalog example (Moonwell) -> HTTP 502 for an unindexed target
  const defaultShown = /Moonwell/.test($("ma-v-title").textContent);
  mode[N.toLowerCase()] = "502"; await submit(N);
  out.default_moonwell_to_502 = defaultShown && isReset(N, "UNAVAILABLE") && /HTTP 502/.test($("ma-v-summary").textContent)
    && !/Moonwell/.test($("ma-v-title").textContent);
  // 2. a successful 2-of-3 Safe A, then a failing B (502)
  await submit(A);
  const aShown = $("ma-v-ctrl").textContent === "2-of-3 Safe" && $("ma-v-title").textContent === sh(A) + " · Ethereum";
  mode[B.toLowerCase()] = "502"; await submit(B);
  out.success_a_then_502_b = aShown && isReset(B, "UNAVAILABLE") && !/2-of-3/.test($("ma-v-ctrl").textContent)
    && !/Live RPC read/.test($("ma-v-prov").textContent);
  // 3. a network rejection
  mode[N.toLowerCase()] = "reject"; await submit(N);
  out.network_rejection = isReset(N, "UNAVAILABLE") && /Network error/.test($("ma-v-summary").textContent);
  // 4. recovery: a successful check renders its own result again
  await submit(A);
  out.recovery = $("ma-verdict").getAttribute("data-ma-status") === "UNINDEXED" && $("ma-v-ctrl").textContent === "2-of-3 Safe"
    && $("ma-v-title").textContent === sh(A) + " · Ethereum" && /Live RPC read/.test($("ma-v-prov").textContent);
  // 5. the loading state shows THIS check (neutral "Checking…"), then the result
  mode[B.toLowerCase()] = "pending"; await submit(B, 1);
  const loading = isReset(B, "CHECKING") && /Reading/.test($("ma-v-summary").textContent);
  if (release) release();
  for (let i = 0; i < 6; i++) await flush();
  out.loading_state = loading && $("ma-v-ctrl").textContent === "2-of-3 Safe" && $("ma-v-title").textContent === sh(B) + " · Ethereum";
  res.ma_reset_transitions = out;
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
    && (!d.getElementById("watch-pilot-target") || d.getElementById("watch-pilot-target").value === "moonwell-lending-base");   // the pilot box is a link card now
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

  let rpcCalls = [], pfCalls = [], weCalls = [], reqCalls = [];
  let reqReply = null;   // P3-CONTACT-03: [status, body] for the next inline watch POSTs; null = a stored 200
  const mockFetch = (url, opts) => {
    const u = String(url);
    if (/\/v1\/requests$/.test(u)) {   // the inline watch card (a local mock; nothing leaves the harness)
      reqCalls.push([u, opts]);
      if (reqReply) return Promise.resolve({ status: reqReply[0], ok: reqReply[0] >= 200 && reqReply[0] < 300, json: () => Promise.resolve(reqReply[1]) });
      return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve({ ok: true, request_id: "REQ-2026-00c0ffee", has_contact_opt_in: true, persisted: true,
        fast_track_url: "https://pacta.wtf/request/?tier=community&protocol=harness-fast-track" }) });
    }
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

  // 1. Demo Treasury Safe chip: instant full multi-position render, then live's progressive $9 report / $0.05 x402 unlock (Section 7)
  //    + the inline free-watchlist link (no alert promise)
  const p = run(input.scan, input.app, { path: "/scan/", fetch: mockFetch });
  const d = p.document;
  const coldOk = d.getElementById("scan-upgrade").hidden === true && d.getElementById("co-card").hidden === true && !d.querySelector("[data-wallet-locked]");
  const demoSafeBtn = d.querySelector('[data-wallet-demo="demo_safe_eth_base"]');
  click(demoSafeBtn);
  for (let i = 0; i < 6; i++) await flush();
  const hl = d.querySelector("[data-wallet-headline]");
  const safeBadge = d.querySelector("[data-wallet-safe-badge]");
  const topGap = d.querySelector("[data-wallet-top-gap]");
  const gapItems = d.querySelectorAll("[data-wallet-gap-item]").map((x) => x.getAttribute("data-wallet-gap-item"));
  const contagion = d.querySelector("[data-wallet-contagion]");
  const inlineWatch = d.querySelector("[data-wallet-result] [data-scan-inline-watch]");
  const b2bBar = d.querySelector("[data-wallet-b2b]");
  const demoOk = coldOk && !!hl && hl.textContent.includes("Found 4 active DeFi positions") && hl.textContent.includes("2 ALIGNED, 2 FLAGGED")
    && !!safeBadge && safeBadge.textContent.includes("Gnosis Safe 3-of-5")
    && !!topGap && topGap.getAttribute("data-wallet-top-gap") === "stader-labs-ethx"
    && !contagion && !!inlineWatch && !!inlineWatch.querySelector("form")
    && !!d.querySelector("[data-wallet-locked]") && !!d.querySelector("[data-wl-unlock-jump]") && !!b2bBar && !b2bBar.textContent.includes("Pool")
    && d.getElementById("scan-upgrade").hidden === false
    && d.getElementById("scan-to-guard").getAttribute("href").includes("../watch/?")
    && d.getElementById("scan-x402-cmd").textContent.includes(demoSafeBtn.getAttribute("data-demo-addr"));

  // the inline watch prompt in the wallet result: the held indexed protocols (up to 10), the promise, email only, the same POST + receipt
  const W = inlineWatch || { querySelector: () => null, querySelectorAll: () => [], textContent: "", getAttribute: () => "", classList: { contains: () => false } };
  const heldSlugs = [...new Set(d.querySelectorAll("[data-wallet-result] [data-pos-slug]").map((x) => x.getAttribute("data-pos-slug")))].slice(0, 10);
  const wTargets = String(W.getAttribute("data-watch-targets") || "").split(",");
  const wEmail = W.querySelector('input[type="email"]'), wBtn = W.querySelector("[data-w-submit]"), wForm = W.querySelector("form");
  const BANNED_W = /\binstant(?:ly)?\b|real[- ]?time|\bautomatic(?:ally)?\b/i;
  const wCopyOk = !!inlineWatch && W.getAttribute("data-slot") === "card" && W.classList.contains("pf-watch-inline")
    && W.querySelector("h3").textContent === "Get notified when this contract's implementation, Safe signers or timelock queue changes"
    && heldSlugs.length >= 1 && wTargets.slice().sort().join() === heldSlugs.slice().sort().join()
    && W.textContent.includes("When one changes, a person at Pacta emails you, normally within 24 hours. We confirm your sign-up by email within 24 hours.")
    && W.textContent.includes("Your email is used only for these alerts, never shared, and removed on request.") && !BANNED_W.test(W.textContent)
    && !!wEmail && wEmail.getAttribute("maxlength") === "120" && wEmail.getAttribute("placeholder") === "you@company.org"
    && !!wBtn && wBtn.textContent === "Watch by email"
    && W.querySelectorAll("a").some((a) => a.getAttribute("href") === "../watch/?protocol=" + wTargets.join(",") && a.textContent === "Pick up to 10 protocols or fund a check on /watch/");
  let wRefused = false, wb = {};
  if (wEmail && wForm) {
    wEmail.value = "user@example.com"; wForm.dispatchEvent(new Event_("submit")); await flush();
    wRefused = reqCalls.length === 0 && /Enter a valid email address/.test(W.querySelector('[data-slot="form-message"]').textContent);
    wEmail.value = "treasury@dao-ops.org"; wForm.dispatchEvent(new Event_("submit")); for (let i = 0; i < 4; i++) await flush();
    wb = reqCalls.length === 1 ? JSON.parse(reqCalls[0][1].body) : {};
  }
  const wDone = W.querySelector("[data-w-done]");
  res.scan_inline_watch_wallet = wCopyOk && wRefused && reqCalls.length === 1 && reqCalls[0][0] === "https://api.pacta.wtf/v1/requests"
    && wb.caller_agent === "pacta-web" && wb.request_type === "mcp_or_api_feature" && wb.urgency_track === "community_queue_free"
    && wb.requester_role === "risk_curator_analyst" && wb.caller_purpose === "governance_monitoring" && wb.contact_handle === "treasury@dao-ops.org"
    && wb.requested_capability === "WATCH watchlist - " + wTargets.join(", ") && /^watch-[a-z0-9-]+-[0-9a-f]{6}$/.test(wb.target_subject || "")
    && wForm.hidden === true && !!wDone && wDone.hidden === false
    && wDone.textContent.includes("Sign-up received \u2014 nothing charged. A person at Pacta will confirm your watch list by email within 24 hours.")
    && !/harness-fast-track/.test(d.body.textContent);
  res.scan_inline_watch_bodies = reqCalls.map((c) => JSON.parse(c[1].body));

  // 2. Dispatch Rule 2: known protocol 0x contract -> single-protocol preflight + 1-click wallet deposit prompt
  const staderAddr = "0xA35b1B31Ce002FBF2058D22F30f95D405200A15b";
  d.getElementById("pf-address").value = staderAddr;
  d.getElementById("pf-form").dispatchEvent(new Event_("submit"));
  for (let i = 0; i < 6; i++) await flush();
  const protoDispatchOk = pfCalls.length === 1 && pfCalls[0].includes(staderAddr)
    && !!d.querySelector("[data-wallet-proto-prompt]");
  // the same inline watch prompt in a contract (preflight) result: the indexed protocol, else <chain>:0x<40 hex>
  const cW = d.querySelector("[data-pf-result] [data-scan-inline-watch]");
  res.scan_inline_watch_contract = !!cW && /^(?:(?:ethereum|base):0xa35b1b31ce002fbf2058d22f30f95d405200a15b|stader-labs-ethx)$/.test(cW.getAttribute("data-watch-targets") || "")
    && cW.querySelector("h3").textContent === "Get notified when this contract's implementation, Safe signers or timelock queue changes"
    && !!cW.querySelector('input[type="email"]') && cW.querySelector("[data-w-submit]").textContent === "Watch by email" && !!cW.querySelector("form")
    && cW.textContent.includes("When one changes, a person at Pacta emails you, normally within 24 hours.") && !BANNED_W.test(cW.textContent)
    && cW.querySelectorAll("a").some((a) => /^\.\.\/watch\/\?(?:chain=(?:ethereum|base)&address=0xa35b1b31ce002fbf2058d22f30f95d405200a15b|protocol=stader-labs-ethx)$/.test(a.getAttribute("href") || ""));
  // P3-CONTACT-03 on the inline card: each not-stored answer keeps the form, the email and no receipt, with the one plain line
  const NOT_SAVED = "We could not confirm whether your submission was saved. Your entries are still here \u2014 please try again, or write to pacta@dri.network.";   // NOT_SAVED_TXT: "could not confirm", never "not saved"
  const cwRes = [];
  if (cW && cW.querySelector("form")) {
    const cf = cW.querySelector("form"), ce = cW.querySelector('input[type="email"]'), cst = cW.querySelector("[data-w-status]"), cd = cW.querySelector("[data-w-done]");
    for (const rr of [[200, { schema: "pacta.demand_receipt.v1", request_id: "REQ-2026-00c0ffee", status: "queued", demand_votes: 1, has_contact_opt_in: false, persisted: false,
                             note: "Queued in Pacta's public demand queue. The contact handle was NOT stored (no private store available); nothing was published." }],
                      [503, { error: "contact_storage_unavailable", detail: "We could not confirm whether your submission was saved. Please try again, or write to pacta@dri.network" }]]) {
      reqReply = rr; const n0 = reqCalls.length;
      ce.value = "treasury@dao-ops.org"; cf.dispatchEvent(new Event_("submit")); for (let i = 0; i < 4; i++) await flush();
      cwRes.push(reqCalls.length === n0 + 1 && cf.hidden !== true && (!cd || cd.hidden === true) && ce.value === "treasury@dao-ops.org"
        && !!cst && cst.hidden === false && cst.textContent === NOT_SAVED && cW.querySelector("[data-w-submit]").disabled === false && !/Sign-up received/.test(cW.textContent));
    }
    reqReply = null;
  }
  res.scan_inline_not_stored_keeps_entries = cwRes.length === 2 && cwRes.every(Boolean);

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
  res.scan_inline_watch_live_wallet = !!d.querySelector("[data-wallet-result] [data-scan-inline-watch] form") && d.querySelectorAll("[data-scan-inline-watch]").length === 1;

  res.wl_demo_and_multicall_fallback = demoOk && protoDispatchOk && fallbackOk;
}
// (w) /watch/ (one page, two asks) + /webhook/ redirect: the combobox (ARIA, ArrowDown / ArrowUp / Enter / Escape / Tab / focusout),
//     quick picks, removable chips, the live "Selected: N / 10" count, 1..10 enforced, ?protocol= / ?address=&chain= prefill, a pasted
//     0x address, email-only contact, the exact intercepted POST /v1/requests bodies (colon-free subject + 6-hex nonce), the neutral
//     receipts (never fast_track_url), and /webhook/?q#h -> location.replace("../watch/?q#h"). Every fetch here is a local mock.
async function watchScenario() {
  if (!input.watch || !input.webhook || !input.lookupJson) { res.watch_error = "no /watch/ input"; return; }
  const API = "https://api.pacta.wtf/v1/requests";
  const REPLY = { schema: "pacta.demand_receipt.v1", ok: true, request_id: "REQ-2026-0a1b2c3d", status: "queued", demand_votes: 1, has_contact_opt_in: true, persisted: true,
                  fast_track_url: "https://pacta.wtf/request/?tier=community&protocol=harness-fast-track", note: "urgent review" };
  let calls = [];
  const mock = (status, body) => (url, opts) => { calls.push([String(url), opts]); return Promise.resolve({ status, ok: status >= 200 && status < 300, json: () => Promise.resolve(body) }); };
  const kd = (elm, k) => { const ev = new Event_("keydown"); ev.key = k; ev.target = elm; elm.dispatchEvent(ev); return ev; };
  const typ = (elm, v) => { elm.value = v; const ev = new Event_("input"); ev.target = elm; elm.dispatchEvent(ev); };
  const fire = (elm, t, extra) => { const ev = Object.assign(new Event_(t), extra || {}); ev.target = elm; elm.dispatchEvent(ev); return ev; };
  const submit = (f) => { const ev = new Event_("submit"); ev.target = f; f.dispatchEvent(ev); return ev; };
  const watchPage = (search, status, body) => run(input.watch, input.app, { path: "/watch/", search: search || "", fetch: mock(status || 200, body || REPLY) });
  const protos = input.lookupJson.items.filter((x) => x.kind === "protocol");
  const KEYS = ["caller_agent", "requester_role", "caller_purpose", "request_type", "target_subject", "requested_capability", "urgency_track", "contact_handle"];
  const bodyOf = (i) => JSON.parse(calls[i][1].body);
  const keysOk = (b) => JSON.stringify(Object.keys(b).sort()) === JSON.stringify(KEYS.slice().sort());
  const subjOk = (s, pre) => typeof s === "string" && s.length >= 2 && s.length <= 120 && !s.includes(":") && new RegExp("^" + pre + "-[0-9a-f]{6}$").test(s);
  const BANNED = /\binstant(?:ly)?\b|real[- ]?time|\bautomatic(?:ally)?\b/i;
  const bodies = [];

  // 1. cold page + keyboard combobox + quick picks + chips + count
  calls = [];
  let p = watchPage(), d = p.document;
  const q = d.getElementById("watch-q"), list = d.getElementById("watch-list"), form = d.getElementById("watch-form");
  const count = () => d.querySelector("[data-watch-count]").textContent;
  const chipNames = () => d.querySelectorAll("#watch-chips .chip-x").map((c) => c.textContent);
  const pickBtn = (label) => d.querySelectorAll("[data-watch-pick]").find((b) => b.textContent === label);
  const opts = list.querySelectorAll('[role="option"]');
  const coldOk = calls.length === 0 && q.getAttribute("role") === "combobox" && q.getAttribute("aria-controls") === "watch-list"
    && q.getAttribute("aria-expanded") === "false" && list.hidden === true && list.getAttribute("aria-multiselectable") === "true"
    && opts.length === protos.length && opts.every((o) => protos.some((x) => x.slug === o.getAttribute("data-slug")))
    && d.querySelectorAll("[data-watch-pick]").map((b) => b.textContent).join("|") === "Ethena|Morpho|Aave v3|Treehouse|Pendle|Lido"
    && count() === "Selected: 0 / 10" && d.getElementById("watch-email").getAttribute("type") === "email"
    && d.getElementById("watch-email").getAttribute("maxlength") === "120" && d.getElementById("watch-email").getAttribute("placeholder") === "you@company.org"
    && d.getElementById("watch-email").getAttribute("autocomplete") === "email" && !d.getElementById("co-form") && !d.querySelector("[data-co-pay]");
  fire(q, "focus");
  const opened = list.hidden === false && q.getAttribute("aria-expanded") === "true";
  typ(q, "ethena"); kd(q, "Enter");
  const enterOk = chipNames().length === 1 && /Ethena/.test(chipNames()[0]) && count() === "Selected: 1 / 10" && pickBtn("Ethena").getAttribute("aria-pressed") === "true";
  kd(q, "Escape");
  const escOk = list.hidden === true && q.getAttribute("aria-expanded") === "false";
  typ(q, "morpho"); kd(q, "ArrowDown"); kd(q, "ArrowUp");
  const activeOk = !!q.getAttribute("aria-activedescendant");
  kd(q, "Enter");
  kd(q, "Tab");
  const tabOk = list.hidden === true && q.getAttribute("aria-expanded") === "false" && count() === "Selected: 2 / 10";
  fire(q, "focus"); fire(d.querySelector("[data-combo]"), "focusout", { relatedTarget: d.getElementById("watch-email") });
  const focusoutOk = list.hidden === true && q.getAttribute("aria-expanded") === "false";
  const morphoBtn = d.querySelectorAll("#watch-chips .chip-x button").find((b) => /^Remove Morpho/.test(b.getAttribute("aria-label") || ""));
  click(morphoBtn);
  click(pickBtn("Lido"));
  const chipsOk = !!morphoBtn && chipNames().length === 2 && pickBtn("Lido").getAttribute("aria-pressed") === "true"
    && pickBtn("Morpho").getAttribute("aria-pressed") === "false" && count() === "Selected: 2 / 10"
    && d.querySelectorAll("#watch-chips .chip-x button").every((b) => /^Remove .+/.test(b.getAttribute("aria-label") || "") && b.getAttribute("type") === "button");
  res.watch_combobox_keyboard_chips = coldOk && opened && enterOk && escOk && activeOk && tabOk && focusoutOk && chipsOk;

  // 2. email only: placeholders, handles, URLs are refused with the exact message and nothing is sent; then the exact Ask 1 body + receipt
  const emailIn = d.getElementById("watch-email"), eErr = d.getElementById("watch-email-err");
  const refused = ["user@example.com", "ops@example.org", "ops@example.net", "a@test.com", "@telegram_handle", "github-handle",
                   "https://hooks.example.invalid/x", "risk@sub.example.com", ""].every((v) => {
    emailIn.value = v; submit(form);
    return calls.length === 0 && eErr.hidden === false && eErr.textContent === "Enter a valid email address. Watch alerts are sent by email only."
      && emailIn.getAttribute("aria-invalid") === "true";
  });
  emailIn.value = "  risk.desk@fund-ops.co  "; submit(form); await flush(); await flush(); await flush();
  const b1 = calls.length === 1 ? bodyOf(0) : {};
  if (calls.length) bodies.push(b1);
  const doneEl = d.querySelector("[data-watch-done]"), doneMsg = d.querySelector("[data-watch-done-msg]");
  res.watch_free_posts_exact_body = refused && calls.length === 1 && calls[0][0] === API && calls[0][1].method === "POST"
    && form.getAttribute("data-api") === API && keysOk(b1)
    && b1.caller_agent === "pacta-web" && b1.requester_role === "risk_curator_analyst" && b1.caller_purpose === "governance_monitoring"
    && b1.request_type === "mcp_or_api_feature" && b1.urgency_track === "community_queue_free" && b1.contact_handle === "risk.desk@fund-ops.co"
    && subjOk(b1.target_subject, "watch-ethena-usde-susde")
    && b1.requested_capability === "WATCH watchlist - ethena-usde-susde, lido-steth-dual-governance"
    && form.hidden === true && doneEl.hidden === false && doneMsg.textContent === "Sign-up received — nothing charged. A person at Pacta will confirm your watch list by email within 24 hours."
    && d.querySelector("[data-watch-done] [data-slot=\"badge\"]").textContent === "Received · Nothing charged"
    && !/harness-fast-track|urgent review|REQ-2026/i.test(d.body.textContent);

  // 3. 0 targets refused; >10 refused (a ?protocol= list keeps the first 10, an 11th pick is refused with a message)
  calls = [];
  p = watchPage(); d = p.document;
  d.getElementById("watch-email").value = "risk.desk@fund-ops.co"; submit(d.getElementById("watch-form")); await flush();
  const zeroOk = calls.length === 0 && d.getElementById("watch-proto-err").hidden === false && /at least one/.test(d.getElementById("watch-proto-err").textContent);
  const twelve = protos.filter((x) => !["lido-steth-dual-governance"].includes(x.slug)).slice(0, 12).map((x) => x.slug);
  calls = [];
  p = watchPage("?protocol=" + twelve.join(",")); d = p.document;
  const tenOk = d.querySelectorAll("#watch-chips .chip-x").length === 10 && d.querySelector("[data-watch-count]").textContent === "Selected: 10 / 10";
  click(d.querySelectorAll("[data-watch-pick]").find((b) => b.textContent === "Lido"));
  const limitOk = d.querySelectorAll("#watch-chips .chip-x").length === 10 && d.getElementById("watch-proto-err").hidden === false
    && /up to 10/.test(d.getElementById("watch-proto-err").textContent);
  d.getElementById("watch-email").value = "risk.desk@fund-ops.co"; submit(d.getElementById("watch-form")); await flush(); await flush(); await flush();
  const b10 = calls.length === 1 ? bodyOf(0) : {};
  if (calls.length) bodies.push(b10);
  res.watch_targets_1_to_10 = zeroOk && tenOk && limitOk && calls.length === 1 && b10.requested_capability.length <= 280
    && b10.requested_capability.indexOf("WATCH watchlist - " + twelve[0]) === 0 && subjOk(b10.target_subject, "watch-" + twelve[0]);

  // 4. prefill: ?address= of an indexed protocol selects it; any other address (and a pasted one) is a <chain>:0x<40 hex> chip
  const eth = input.lookupJson.items.find((x) => x.slug === "ethena-usde-susde").preflightArgs;
  p = watchPage("?address=" + eth.address + "&chain=" + eth.chain); d = p.document;
  const addrIndexed = d.querySelectorAll("#watch-chips .chip-x").length === 1 && /Ethena/.test(d.querySelector("#watch-chips .chip-x").textContent)
    && d.querySelectorAll("[data-watch-pick]").find((b) => b.textContent === "Ethena").getAttribute("aria-pressed") === "true";
  const RAW = "0x" + "12".repeat(20);
  calls = [];
  p = watchPage("?address=" + RAW + "&chain=base"); d = p.document;
  const rawChip = d.querySelectorAll("#watch-chips .chip-x").length === 1 && d.getElementById("watch-chain").value === "base"
    && /^base:0x1212/.test(d.querySelector("#watch-chips .chip-x").textContent);
  const q2 = d.getElementById("watch-q");
  d.getElementById("watch-chain").value = "ethereum"; typ(q2, "0x" + "ab".repeat(20));
  const pasted = d.querySelectorAll("#watch-chips .chip-x").length === 2 && q2.value === "" && d.getElementById("watch-list").hidden === true;
  d.getElementById("watch-email").value = "risk.desk@fund-ops.co"; submit(d.getElementById("watch-form")); await flush(); await flush(); await flush();
  const bA = calls.length === 1 ? bodyOf(0) : {};
  if (calls.length) bodies.push(bA);
  res.watch_free_address_subject = addrIndexed && rawChip && pasted && calls.length === 1 && subjOk(bA.target_subject, "watch-base-0x12121212")
    && bA.requested_capability === "WATCH watchlist - base:" + RAW + ", ethereum:0x" + "ab".repeat(20);
  calls = [];
  p = watchPage("?protocol=ethena-usde-susde"); d = p.document;
  d.getElementById("watch-email").value = "risk.desk@fund-ops.co"; submit(d.getElementById("watch-form")); await flush(); await flush(); await flush();
  const bN = calls.length === 1 ? bodyOf(0) : {};
  res.watch_nonce_per_submission = !!bN.target_subject && !!b1.target_subject && bN.target_subject !== b1.target_subject
    && bN.target_subject.slice(0, -7) === b1.target_subject.slice(0, -7);
  // a refused or failed request never shows the receipt
  calls = [];
  p = watchPage("?protocol=ethena-usde-susde", 429, { error: "rate_limited" }); d = p.document;
  d.getElementById("watch-email").value = "risk.desk@fund-ops.co"; submit(d.getElementById("watch-form")); await flush(); await flush(); await flush();
  res.watch_error_no_receipt = calls.length === 1 && d.querySelector("[data-watch-done]").hidden === true && d.getElementById("watch-form").hidden !== true
    && /Too many requests/.test(d.querySelector("#watch-form [data-w-status]").textContent);

  // 5. Ask 2 pledge: 3 fields, 25..500 whole USDC, email only, target without personal data; the exact body; no watchlist word
  calls = [];
  p = watchPage(); d = p.document;
  const pf = d.getElementById("pledge-form"), pt = d.getElementById("pledge-target"), pa = d.getElementById("pledge-amount"), pe = d.getElementById("pledge-email");
  const shapeOk = pf.querySelectorAll("input").length === 3 && pa.getAttribute("type") === "number" && pa.getAttribute("min") === "25"
    && pa.getAttribute("max") === "500" && pa.getAttribute("step") === "1" && pa.getAttribute("placeholder") === "25"
    && pe.getAttribute("type") === "email" && pe.getAttribute("maxlength") === "120" && pe.getAttribute("placeholder") === "you@company.org"
    && pf.getAttribute("data-api") === API;
  const tryP = (t, a, e) => { pt.value = t; pa.value = a; pe.value = e; submit(pf); return calls.length === 0; };
  const pledgeRefused = tryP("", "25", "fund@desk.co") && !d.getElementById("pledge-target-err").hidden
    && tryP("Aave", "24", "fund@desk.co") && !d.getElementById("pledge-amount-err").hidden
    && tryP("Aave", "501", "fund@desk.co") && tryP("Aave", "25.5", "fund@desk.co") && tryP("Aave", "", "fund@desk.co")
    && tryP("me@vault.org", "25", "fund@desk.co") && tryP("@vaultdesk", "25", "fund@desk.co") && tryP("ab".repeat(32), "25", "fund@desk.co")
    && tryP("https://user:pw@host.example.invalid/x", "25", "fund@desk.co") && tryP("0x1234", "25", "fund@desk.co")
    && tryP("Aave", "25", "@telegram") && !d.getElementById("pledge-email-err").hidden && tryP("Aave", "25", "user@example.com");
  pt.value = "  Aave V3 / GHO  "; pa.value = "25"; pe.value = "fund@desk.co"; submit(pf); await flush(); await flush(); await flush();
  const bP = calls.length === 1 ? bodyOf(0) : {};
  if (calls.length) bodies.push(bP);
  res.watch_pledge_exact_body = shapeOk && pledgeRefused && calls.length === 1 && calls[0][0] === API && keysOk(bP)
    && bP.caller_agent === "pacta-web" && bP.requester_role === "institutional_allocator" && bP.caller_purpose === "collateral_due_diligence"
    && bP.request_type === "missing_check_surface" && bP.urgency_track === "active_due_diligence" && bP.contact_handle === "fund@desk.co"
    && subjOk(bP.target_subject, "pledge-aave-v3-gho") && bP.requested_capability === "PLEDGE pool check 25 USDC - Aave V3 / GHO"
    && pf.hidden === true && d.querySelector("[data-pledge-done]").hidden === false
    && d.querySelector("[data-pledge-done-msg]").textContent === "Pledge received — nothing charged. We will reply by email to agree the scope before sending any Safe deposit address."
    && !/harness-fast-track|urgent review|issuer_urgent_review/i.test(d.body.textContent);
  calls = [];
  p = watchPage(); d = p.document;
  d.getElementById("pledge-target").value = "My Watchlist vault"; d.getElementById("pledge-amount").value = "500"; d.getElementById("pledge-email").value = "fund@desk.co";
  submit(d.getElementById("pledge-form")); await flush(); await flush(); await flush();
  const bW = calls.length === 1 ? bodyOf(0) : {};
  if (calls.length) bodies.push(bW);
  calls = [];
  p = watchPage(); d = p.document;
  d.getElementById("pledge-target").value = "0x" + "Cd".repeat(20); d.getElementById("pledge-amount").value = "120"; d.getElementById("pledge-email").value = "fund@desk.co";
  submit(d.getElementById("pledge-form")); await flush(); await flush(); await flush();
  const bX = calls.length === 1 ? bodyOf(0) : {};
  if (calls.length) bodies.push(bX);
  res.watch_pledge_never_watchlist = !!bW.requested_capability && !/watchlist/i.test(bW.requested_capability) && bW.requested_capability.indexOf("PLEDGE pool check 500 USDC - ") === 0
    && subjOk(bX.target_subject, "pledge-0xcdcdcdcd") && bX.requested_capability === "PLEDGE pool check 120 USDC - 0x" + "Cd".repeat(20);

  // 6. copy: the promise, both privacy lines, custody (future tense) and firewall; no banned words, no price, no Safe address
  const txt = d.body.textContent;
  res.watch_copy_honest = txt.includes("We read the timelocks and admin roles of the protocols you pick. When one changes, a person at Pacta emails you, normally within 24 hours. We confirm your sign-up by email within 24 hours.")
    && txt.includes("Your email is used only for these alerts, never shared, and removed on request.")
    && txt.includes("Your email is used only for this check, never shared, and removed on request.")
    && txt.includes("When a check is agreed, the money goes into a two-signature Safe on Base (the founder's wallet plus an independent verifier's key; neither can move funds alone), with a limit of 500 USDC in total. Nothing is paid on this page; the Safe address is sent directly by email once the scope is agreed.")
    && txt.includes("Contributions fund verification work only and never change a finding.")
    && !BANNED.test(txt) && !/are held|\$\d|\/ ?mo\b|0x[0-9a-fA-F]{40}|eth_sendTransaction/.test(txt)
    && d.querySelectorAll("a").some((a) => a.getAttribute("href") === "../feed.xml") && d.querySelectorAll("a").some((a) => a.getAttribute("href") === "../radar/");

  // 7. /webhook/ -> /watch/ with the query and hash kept
  const rp = run(input.webhook, input.app, { path: "/webhook/", search: "?address=" + RAW + "&chain=base", hash: "#fund-check" });
  const rp0 = run(input.webhook, input.app, { path: "/webhook/" });
  res.webhook_redirects_to_watch = rp.location.replaced === "../watch/?address=" + RAW + "&chain=base#fund-check" && rp0.location.replaced === "../watch/"
    && rp.document.body.getAttribute("data-redirect-watch") === "../watch/";
  res.watch_bodies = bodies;

  // 8. WATCH-TIMEOUT-03: a POST that never answers is cut at the 30 s deadline (the request is aborted); the form unlocks with its entries
  //    kept and says delivery could not be confirmed; 0 automatic resend; the deadline timer is cleared; a later manual submit goes through
  const TIMEOUT_TXT = "We could not confirm delivery in time. Your entries are still here: try again, or email pacta@dri.network directly.";
  const toRes = [];
  for (const which of ["watch", "pledge"]) {
    const timers = []; let hang = true, aborted = 0;
    calls = [];
    const fetchT = (url, o) => {
      calls.push([String(url), o]);
      if (!hang) return Promise.resolve({ status: 200, ok: true, json: () => Promise.resolve(REPLY) });
      return new Promise((_, rej) => { if (o && o.signal) o.signal.addEventListener("abort", () => { aborted++; rej(new Error("AbortError")); }); });
    };
    p = run(input.watch, input.app, { path: "/watch/", search: which === "watch" ? "?protocol=ethena-usde-susde" : "", fetch: fetchT,
      setTimeout: (fn, ms) => { timers.push({ fn, ms: ms || 0, live: true }); return timers.length; },
      clearTimeout: (id) => { if (timers[id - 1]) timers[id - 1].live = false; } });
    d = p.document;
    const f = d.getElementById(which + "-form"), btn = f.querySelector("[data-w-submit]"), st = f.querySelector("[data-w-status]");
    const vals = () => f.querySelectorAll("input").map((x) => x.value).join("|");
    if (which === "watch") d.getElementById("watch-email").value = "risk.desk@fund-ops.co";
    else { d.getElementById("pledge-target").value = "Aave V3 / GHO"; d.getElementById("pledge-amount").value = "25"; d.getElementById("pledge-email").value = "fund@desk.co"; }
    const before = vals(), chipsBefore = d.querySelectorAll("#watch-chips .chip-x").length;
    submit(f); for (let i = 0; i < 4; i++) await flush();
    const busyOk = btn.disabled === true && btn.getAttribute("aria-busy") === "true" && calls.length === 1;
    const dl = timers.filter((t) => t.live && t.ms === 30000);
    dl.forEach((t) => { t.live = false; t.fn(); });
    for (let i = 0; i < 6; i++) await flush();
    const unlockOk = dl.length === 1 && aborted === 1 && btn.disabled === false && !btn.hasAttribute("aria-busy") && st.hidden === false
      && st.textContent === TIMEOUT_TXT && f.hidden !== true && d.querySelector("[data-" + which + "-done]").hidden === true
      && vals() === before && d.querySelectorAll("#watch-chips .chip-x").length === chipsBefore && calls.length === 1;
    for (let i = 0; i < 6; i++) await flush();
    const noRetry = calls.length === 1 && timers.filter((t) => t.live && t.ms >= 1000).length === 0;
    hang = false; submit(f); for (let i = 0; i < 6; i++) await flush();
    const manualOk = calls.length === 2 && f.hidden === true && d.querySelector("[data-" + which + "-done]").hidden === false
      && timers.filter((t) => t.live && t.ms === 30000).length === 0 && calls[1][1].body !== calls[0][1].body
      && !!calls[0][1].signal && JSON.parse(calls[1][1].body).contact_handle === JSON.parse(calls[0][1].body).contact_handle;
    toRes.push(busyOk && unlockOk && noRetry && manualOk);
  }
  res.watch_submit_timeout_unlocks = toRes.length === 2 && toRes.every(Boolean);

  // 8b. P3-CONTACT-03: "Received" only when the answer says the email was stored. Live 069b6222 with a failed private store answers 200
  //     persisted:false / has_contact_opt_in:false (or, on an upvote, a "NOT stored" note); the updated Worker answers 503. Each keeps the
  //     form visible with every chip and entry, shows no receipt, re-enables the button and shows the one plain line (published address only).
  const NOT_SAVED = "We could not confirm whether your submission was saved. Your entries are still here \u2014 please try again, or write to pacta@dri.network.";   // NOT_SAVED_TXT: "could not confirm", never "not saved"
  const STORED_NOTE = "Queued in Pacta's public demand queue. The contact handle was stored privately (never published) for follow-up. No GitHub issue is opened and nothing is charged; fast_track_url is optional.";
  const NOT_STORED_NOTE = "Queued in Pacta's public demand queue. The contact handle was NOT stored (no private store available); nothing was published. No GitHub issue is opened and nothing is charged; fast_track_url is optional.";
  const R = { schema: "pacta.demand_receipt.v1", request_id: "REQ-2026-0a1b2c3d", status: "queued", demand_votes: 1 };
  const SHAPES = {
    persisted_false: [200, { ...R, has_contact_opt_in: false, persisted: false, note: NOT_STORED_NOTE }],
    opt_in_false: [200, { ...R, has_contact_opt_in: false, persisted: true, note: STORED_NOTE }],
    note_not_stored: [200, { ...R, status: "upvoted_existing", demand_votes: 3, has_contact_opt_in: true, persisted: true, note: NOT_STORED_NOTE }],
    flags_missing: [200, { ...R, ok: true }],
    http_503: [503, { error: "contact_storage_unavailable", detail: "We could not confirm whether your submission was saved. Please try again, or write to pacta@dri.network" }],
  };
  const nsRes = {};
  for (const which of ["watch", "pledge"]) {
    for (const [name, [st0, body0]] of Object.entries({ ...SHAPES, stored: [200, { ...R, has_contact_opt_in: true, persisted: true, note: STORED_NOTE }] })) {
      calls = [];
      p = watchPage(which === "watch" ? "?protocol=ethena-usde-susde,lido-steth-dual-governance" : "", st0, body0); d = p.document;
      const f = d.getElementById(which + "-form"), btn = f.querySelector("[data-w-submit]"), st = f.querySelector("[data-w-status]"), done = d.querySelector("[data-" + which + "-done]");
      if (which === "watch") { d.getElementById("watch-chain").value = "base"; typ(d.getElementById("watch-q"), "0x" + "ab".repeat(20)); d.getElementById("watch-email").value = "risk.desk@fund-ops.co"; }
      else { d.getElementById("pledge-target").value = "Aave V3 / GHO"; d.getElementById("pledge-amount").value = "120"; d.getElementById("pledge-email").value = "fund@desk.co"; }
      const vals = () => f.querySelectorAll("input").map((x) => x.value).join("|"), chips = () => d.querySelectorAll("#watch-chips .chip-x").map((c) => c.textContent).join("|");
      const before = vals(), chipsBefore = chips();
      submit(f); for (let i = 0; i < 6; i++) await flush();
      if (name === "stored") {
        nsRes[which + ":" + name] = calls.length === 1 && f.hidden === true && done.hidden === false && (!st || st.hidden === true || st.textContent === "")
          && !d.body.textContent.includes(NOT_SAVED);
      } else {
        nsRes[which + ":" + name] = calls.length === 1 && f.hidden !== true && done.hidden === true && btn.disabled === false && !btn.hasAttribute("aria-busy")
          && st.hidden === false && st.textContent === NOT_SAVED && vals() === before && chips() === chipsBefore
          && (which !== "watch" || chipsBefore.split("|").length === 3)
          && !/Sign-up received|Pledge received/.test(d.querySelector("#" + which + "-form").textContent + (st.textContent || ""));
      }
    }
  }
  res.watch_not_stored_results = nsRes;
  res.watch_not_stored_keeps_entries = Object.keys(nsRes).length === 12 && Object.values(nsRes).every(Boolean);

  // 9. WATCH-FOCUS-01: the /scan/ address list closes on Tab and when focus leaves the combobox (to the next button, or to nowhere)
  const sp = run(input.scan, input.app, { path: "/scan/", fetch: (url) => /api\/v1\/lookup\.json$/.test(String(url))
    ? Promise.resolve({ status: 200, json: () => Promise.resolve(input.lookupJson) }) : Promise.reject(new Error("blocked")),
    setTimeout: (fn, ms) => { if (!ms) Promise.resolve().then(() => { try { fn(); } catch (e) { /* init re-throw: ignored */ } }); return 0; } });
  const sd = sp.document, sInp = sd.getElementById("pf-address"), sLb = sd.getElementById("pf-listbox"), sCombo = sd.querySelector("[data-pf-combo]");
  const sOpen = async () => { fire(sInp, "focus"); for (let i = 0; i < 5; i++) await flush(); return sLb.hidden === false && sInp.getAttribute("aria-expanded") === "true"; };
  const sClosed = () => sLb.hidden === true && sInp.getAttribute("aria-expanded") === "false";
  const o1 = await sOpen(); const tabEv = kd(sInp, "Tab"); const c1 = sClosed() && !tabEv.defaultPrevented;
  const nextBtn = sd.querySelector("[data-pf-try], [data-wallet-demo], #pf-submit");
  const o2 = await sOpen(); fire(sCombo, "focusout", { relatedTarget: nextBtn }); const c2 = sClosed();
  const o3 = await sOpen(); fire(sCombo, "focusout", { relatedTarget: sd.getElementById("pf-combo-clear") }); const kept = sLb.hidden === false;
  fire(sCombo, "focusout", { relatedTarget: null }); for (let i = 0; i < 3; i++) await flush(); const c3 = sClosed();
  const o4 = await sOpen(); kd(sInp, "ArrowDown"); const act = !!sInp.getAttribute("aria-activedescendant"); kd(sInp, "Escape"); const c4 = sClosed();
  res.scan_combo_tab_focusout_closes = o1 && c1 && !!nextBtn && o2 && c2 && o3 && kept && c3 && o4 && act && c4;
}
// ---------- /check/ (Who controls this contract?): every RPC answer comes from tools/check_fixtures.json ----------
// The fixtures are real read-only JSON-RPC results recorded from the four public providers (block objects trimmed to number and
// hash). Tampered answers (disagreement, errors, timeouts, the latest fallback) are built here from those records, per test.
async function checkScenario() {
  if (!input.check || !input.checkFixtures) { res.check_error = "no /check/ input"; return; }
  const FX = input.checkFixtures;
  const URLS = { ethereum: ["https://ethereum-rpc.publicnode.com", "https://eth.drpc.org"], base: ["https://mainnet.base.org", "https://base-rpc.publicnode.com"] };
  const chainOf = (u) => (URLS.ethereum.includes(u) ? "ethereum" : URLS.base.includes(u) ? "base" : null);
  const recorded = (u, m, p) => (m === "eth_getBlockByNumber" ? FX.byUrl[u + " " + m + " " + JSON.stringify(p)] : FX.byChain[chainOf(u) + " " + m + " " + JSON.stringify(p)]);
  // the brief's gate: no rating words, and "safe" only as the capitalised name (Gnosis Safe / Safe multisig)
  const GATE = /\b(unsafe|insecure|risk\s*score|grade)\b/i, SAFE_ADJ = /\bsafe\b/, MORE = /\b(secure|immutable|warning|risk|risky|rating|score|graded)\b/i;
  const gateOk = (t) => !GATE.test(t) && !SAFE_ADJ.test(t) && !MORE.test(t);
  const gateSelf = !gateOk("this vault is safe") && !gateOk("Unsafe admin") && !gateOk("risk score 7") && !gateOk("Grade A") && !gateOk("insecure")
    && !gateOk("immutable") && gateOk("3-of-6 Safe multisig (0x6d46…51af) · 6 owners · no Safe guard") && gateOk("a Gnosis Safe");
  const gateBad = [];

  function page(opts) {
    opts = opts || {};
    const log = [], misses = [], timers = new Map(); let tid = 0;
    const fetch = (url, init) => {
      const u = String(url), q = JSON.parse(init.body);
      log.push({ u, m: q.method, p: q.params });
      if (!chainOf(u) || init.method !== "POST") return Promise.reject(new Error("blocked host"));
      let out = { result: recorded(u, q.method, q.params) };
      if (out.result === undefined) { misses.push(q.method + " " + JSON.stringify(q.params).slice(0, 80)); out = { error: { code: -32000, message: "no fixture" } }; }
      if (opts.tamper) { const t = opts.tamper(u, q.method, q.params, out.result); if (t) out = t; }
      if (out.hang) return new Promise(() => {});
      const status = out.status || 200;
      const body = out.error ? { jsonrpc: "2.0", id: 1, error: out.error } : { jsonrpc: "2.0", id: 1, result: out.result };
      return Promise.resolve({ status, ok: status === 200, json: () => Promise.resolve(body) });
    };
    const setTimeout_ = (fn, ms) => { const id = ++tid; timers.set(id, { fn, ms: ms || 0 }); return id; };
    const clearTimeout_ = (id) => { timers.delete(id); };
    const p = run(input.check, input.app, { path: "/check/", hostname: opts.hostname || "127.0.0.1", search: opts.search || "", fetch,
      setTimeout: setTimeout_, clearTimeout: clearTimeout_, win: opts.win });
    const d = p.document;
    const fire = (pred) => { for (const [id, t] of Array.from(timers)) if (pred(t)) { timers.delete(id); t.fn(); } };
    const st = () => d.getElementById("ck-status");
    const settle = async () => {
      for (let i = 0; i < 400; i++) {
        await flush(); fire((t) => t.ms === 0);
        if (!d.querySelector("[data-ck-submit]").disabled) break;
      }
    };
    const submit = async (chain, address) => {
      d.getElementById("ck-chain").value = chain; d.getElementById("ck-address").value = address;
      const ev = new Event_("submit"); ev.target = d.getElementById("ck-form"); d.getElementById("ck-form").dispatchEvent(ev);
      await settle(); return ev;
    };
    const out = () => d.getElementById("ck-out");
    const rows = () => {
      const o = {};
      out().querySelectorAll("[data-ck-row]").forEach((r) => {
        const dd = r.querySelector("dd");
        o[r.getAttribute("data-ck-row")] = { t: dd ? dd.textContent.replace(/Copy/g, "") : "", a: dd ? dd.querySelectorAll("[data-copy]").map((b) => b.getAttribute("data-copy")) : [] };
      });
      return o;
    };
    const text = () => out().textContent + " " + st().textContent;
    const pin = () => (out().querySelector("[data-ck-pin]") || { textContent: "" }).textContent;
    const cast = () => out().querySelectorAll(".term pre").map((x) => x.textContent).join("\n");
    const watch = () => { const a = out().querySelector("[data-ck-watch]"); return a ? a.getAttribute("href") : null; };
    return { p, d, log, misses, timers, fire, st, settle, submit, out, rows, text, pin, cast, watch };
  }
  const row = (r, k) => r[k] || { t: "", a: [] };
  const has = (r, k, s) => row(r, k).t.includes(s);
  const addr = (r, k, a) => row(r, k).a.map((x) => x.toLowerCase()).includes(a.toLowerCase());
  const ETH_PIN = "Ethereum · block #26,491,866 (0x77fbf13ed7493d7a6c784fc3d43481763952f365f653cd9c948ab20dfe0f0533) · finalized";
  const BASE_PIN = "Base · block #62,069,007 (0x182e19d0f5c17a88508f1fb730f73f01db0e20f89e8221574730832f058e3ab0) · finalized";
  const DIS = "providers disagree, could not read", ABS = "not exposed on this contract (or reverted)";
  const allSecPins = (pg, want) => pg.out().querySelectorAll("[data-ck-pin]").length >= 1 && pg.out().querySelectorAll(".ck-pin").every((x) => x.textContent === want);
  const live = async (c, extra) => {
    const pg = page(extra);
    await pg.submit(FX.cases[c].chain, FX.cases[c].address);
    const t = pg.text(); if (!gateOk(t)) gateBad.push(c + ": " + (t.match(GATE) || t.match(SAFE_ADJ) || t.match(MORE))[0]);
    return pg;
  };
  const hostsOk = (pg, chain) => pg.log.length > 0 && pg.log.every((x) => URLS[chain].includes(x.u)) && URLS[chain].every((u) => pg.log.some((x) => x.u === u));

  // 1. Maple PoolPermissionManager: EIP-1967 proxy, admin slot = 4-of-7 Safe
  const maple = await live("maple_ppm"); const mr = maple.rows();
  res.check_maple_proxy_admin_safe = maple.misses.length === 0 && maple.pin() === ETH_PIN && allSecPins(maple, ETH_PIN) && hostsOk(maple, "ethereum")
    && has(mr, "Upgrade proxy", "EIP-1967 implementation slot") && has(mr, "Upgrade proxy", "EIP-1967 admin slot")
    && has(mr, "Upgrade admin", "4-of-7 Safe multisig") && has(mr, "Upgrade admin", "7 owners") && has(mr, "owner()", ABS)
    && maple.st().textContent === "Done: Ethereum block #26,491,866.";
  if (!res.check_maple_proxy_admin_safe) res.check_maple_detail = JSON.stringify({ m: maple.misses, pin: maple.pin(), up: row(mr, "Upgrade admin") }).slice(0, 300);

  // 2. Usual RegistryAccess: proxy + ProxyAdmin -> 8-of-15 Safe; defaultAdmin() / defaultAdminDelay(); non-enumerable AccessControl
  const usual = await live("usual_registry_access"); const ur = usual.rows();
  res.check_usual_proxyadmin_safe = usual.misses.length === 0 && usual.pin() === ETH_PIN
    && has(ur, "Upgrade admin", "contract (") && has(ur, "Upgrade admin", "whose owner() is 8-of-15 Safe multisig") && has(ur, "Upgrade admin", "15 owners")
    && has(ur, "defaultAdmin()", "8-of-15 Safe multisig") && row(ur, "defaultAdminDelay()").t === "1 second"
    && row(ur, "DEFAULT_ADMIN_ROLE holders").t === "not determined"
    && row(ur, "Roles").t === "uses role-based AccessControl; role holders could not be read without event logs"
    && usual.cast().includes('cast call ') && usual.cast().includes('"owner()(address)" --block 26491866');
  // the two selectors the brief names are probed by the multicall
  const usualCalls = usual.log.filter((x) => x.m === "eth_call").map((x) => String(x.p[0].data)).join("");
  res.check_usual_default_admin_selectors = usualCalls.includes("84ef8ffc") && usualCalls.includes("cc8463c8");

  // 3. Ethena TimelockController: getMinDelay() = 86400
  const eth = await live("ethena_timelock"); const er = eth.rows();
  res.check_timelock_min_delay = eth.misses.length === 0 && has(er, "This address", "TimelockController")
    && has(er, "This address", "minimum delay 86,400 seconds (1 day)") && has(er, "This address", "proposers: not determined")
    && has(er, "This address", "executors: not determined") && eth.cast().includes('"getMinDelay()(uint256)"');

  // 4. Lagoon beacon: implementation() + owner() = 3-of-6 Safe; 5. the beacon-proxy vault reaches the same Safe through the beacon slot
  const SAFE6 = "0x6D46e28aB34622d9A39d0F306a37a8dC270951aF";
  const lb = await live("lagoon_beacon"); const lbr = lb.rows();
  res.check_beacon_owner_safe = lb.misses.length === 0 && row(lbr, "Upgrade proxy").t === "No proxy slot is set; implementation() on this address returned an address (the shape of an upgrade beacon)"
    && row(lbr, "implementation()").a.length === 1 && has(lbr, "owner()", "3-of-6 Safe multisig") && addr(lbr, "owner()", SAFE6)
    && row(lbr, "Who can upgrade").t.indexOf("not determined from getter reads alone") === 0;
  const lv = await live("lagoon_vault"); const lvr = lv.rows();
  res.check_beacon_proxy_vault = lv.misses.length === 0 && has(lvr, "Upgrade proxy", "EIP-1967 beacon slot")
    && addr(lvr, "Beacon", "0x707D622cdA4b5459e7DcEe8Ba8E429F154f96A27") && row(lvr, "Beacon implementation()").a.length === 1
    && has(lvr, "Beacon owner()", "3-of-6 Safe multisig") && addr(lvr, "Beacon owner()", SAFE6)
    && has(lvr, "paused()", "false") && row(lvr, "pause() in bytecode").t === "selector observed in bytecode: pause()" && has(lvr, "totalSupply()", "18 decimals")
    && row(lvr, "Pause role holders").t === "not determined" && row(lvr, "Mint role holders").t === "not determined"
    && has(lvr, "Upgrade admin", "Who can change the beacon's implementation(): not determined");

  // 6. token: USDC on Base (ZeppelinOS slots, pauser(), masterMinter(), totalSupply(), a mint selector)
  const usdc = await live("usdc_base"); const usr = usdc.rows();
  res.check_token_minter_pauser_supply = usdc.misses.length === 0 && usdc.pin() === BASE_PIN && hostsOk(usdc, "base")
    && has(usr, "Upgrade proxy", "ZeppelinOS implementation slot") && has(usr, "pauser()", "externally owned account")
    && has(usr, "masterMinter()", "contract (") && has(usr, "totalSupply()", " USDC (raw ") && has(usr, "totalSupply()", "6 decimals")
    && row(usr, "Mint functions in bytecode").t === "selector observed in bytecode: mint(address,uint256)"
    && row(usr, "Can supply grow?").t.indexOf("not determined from static bytecode and getter reads alone. Observed: a mint selector was observed in the bytecode; masterMinter() returned an address") === 0
    && has(usr, "paused()", "false: not paused");
  // Base's providers were one finalized block apart when recorded: the lower height is pinned and its hash compared on both
  res.check_pin_lower_height = usdc.log.filter((x) => x.m === "eth_getBlockByNumber" && x.p[0] === "0x3b3190f").length === 2;

  // 7. examples: rETH (no proxy, no standard mint) and the Inverse Policy Committee Safe
  const reth = await live("reth"); const rr = reth.rows();
  const inv = await live("inverse_policy_safe"); const ir = inv.rows();
  res.check_examples_read = reth.misses.length === 0 && inv.misses.length === 0 && has(rr, "Upgrade proxy", "No standard proxy slot is set")
    && has(rr, "Can supply grow?", "custom mint logic not ruled out") && has(ir, "This address", "3-of-6 Safe multisig") && has(ir, "This address", "no Safe guard");

  // 8. EOA (0x…dEaD): the exact sentence, and nothing past the code read
  const eoa = await live("eoa_dead"); const eor = eoa.rows();
  res.check_eoa_message = eoa.misses.length === 0
    && row(eor, "eth_getCode").t === "No contract code at this address on Ethereum at block #26,491,866 (externally owned account or not deployed)."
    && Object.keys(eor).length === 1 && !eoa.out().textContent.includes("Upgrade admin");
  // EIP-7702 delegated EOA: code 0xef0100 || address (built from the EOA record, only the code answer differs)
  const D7702 = "0xef0100" + "77".repeat(20);   // a synthetic delegate, only to exercise the 0xef0100 prefix
  const e7702 = await live("eoa_dead", { tamper: (u, m, p) => (m === "eth_getCode" ? { result: D7702 } : null) });
  res.check_eoa_7702 = /EIP-7702/.test(e7702.out().textContent) && e7702.out().textContent.includes("0x7777");

  // 9. nonsense input: an inline error and zero RPC calls
  const bad = page();
  await bad.submit("ethereum", "not an address");
  await bad.submit("ethereum", "0x12345");
  await bad.submit("base", "0xZZ10aDcE8B6E3E02Db384E7FaDA5395DD113D8b3");
  res.check_nonsense_zero_rpc = bad.log.length === 0 && bad.d.getElementById("ck-address-err").hidden === false
    && bad.d.getElementById("ck-address-err").textContent === "Enter a contract or token address: 0x followed by 40 hexadecimal characters."
    && bad.d.getElementById("ck-address").getAttribute("aria-invalid") === "true" && bad.out().textContent === "";

  // 10. disagreement: B answers a different block hash -> no fact at all; B answers a different slot / call -> that row only
  const B = URLS.ethereum[1];
  const flipHash = (h) => h.slice(0, -1) + (h.slice(-1) === "0" ? "1" : "0");
  const dPin = await live("maple_ppm", { tamper: (u, m, p, r) => (u === B && m === "eth_getBlockByNumber" && r ? { result: { number: r.number, hash: flipHash(r.hash) } } : null) });
  res.check_disagree_block_hash = dPin.st().textContent === DIS + "." && (dPin.out().querySelector("[data-ck-fail]") || {}).textContent === "Block: " + DIS
    && dPin.out().querySelectorAll("[data-ck-row]").length === 0 && !!dPin.watch();
  const ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103";
  const dSlot = await live("maple_ppm", { tamper: (u, m, p, r) => (u === B && m === "eth_getStorageAt" && p[1] === ADMIN_SLOT ? { result: "0x" + "0".repeat(24) + "1".repeat(40) } : null) });
  const dsr = dSlot.rows();
  res.check_disagree_row_only = row(dsr, "EIP-1967 admin slot").t === DIS && row(dsr, "Upgrade admin").t === DIS
    && has(dsr, "Upgrade proxy", "EIP-1967 implementation slot") && dSlot.pin() === ETH_PIN;
  const dCall = await live("usual_registry_access", { tamper: (u, m, p, r) => (u === B && m === "eth_call" && typeof r === "string" && r.length > 200 ? { result: r.slice(0, -2) + (r.slice(-2) === "00" ? "01" : "00") } : null) });
  const dcr = dCall.rows();
  res.check_disagree_getters = row(dcr, "owner()").t === DIS && row(dcr, "totalSupply()").t === DIS && row(dcr, "eth_getCode").t.includes("bytes of contract code");

  // 11. RPC errors: a JSON-RPC error, HTTP 429 and a timeout each read "could not read (<reason>)"
  const eCode = await live("reth", { tamper: (u, m) => (u === B && m === "eth_getCode" ? { error: { code: -32603, message: "internal" } } : null) });
  const e429 = await live("reth", { tamper: (u, m) => (u === B && m === "eth_getBlockByNumber" ? { status: 429 } : null) });
  const eTo = page({ tamper: (u, m) => (u === B && m === "eth_getStorageAt" ? { hang: true } : null) });
  eTo.submit("ethereum", FX.cases.reth.address);
  await eTo.settle();
  let waitingTimers = 0;
  for (let i = 0; i < 6; i++) {
    const n = Array.from(eTo.timers.values()).filter((t) => t.ms === 8000).length; if (!n) break;
    waitingTimers += n; eTo.fire((t) => t.ms === 8000); await eTo.settle();
  }
  const tor = eTo.rows();
  res.check_rpc_error_could_not_read = row(eCode.rows(), "eth_getCode").t === "could not read (RPC error -32603)" && eCode.pin() === ETH_PIN
    && eCode.out().querySelectorAll("[data-ck-row]").length === 1 && !!eCode.watch();
  res.check_rpc_rate_limit = e429.st().textContent === "could not read (RPC rate limit)." && (e429.out().querySelector("[data-ck-fail]") || {}).textContent === "Block: could not read (RPC rate limit)";
  res.check_rpc_timeout = waitingTimers >= 7 && eTo.st().textContent.indexOf("Done:") === 0 && row(tor, "EIP-1967 admin slot").t === "could not read (RPC timeout)"
    && row(tor, "Upgrade admin").t === "could not read (RPC timeout)" && !has(tor, "Upgrade proxy", "No standard proxy slot");
  // finalized unsupported (a JSON-RPC error on both) -> latest, labelled
  const lat = await live("ethena_timelock", { tamper: (u, m, p) => {
    if (m !== "eth_getBlockByNumber") return null;
    if (p[0] === "finalized") return { error: { code: -32602, message: "unsupported block tag" } };
    if (p[0] === "latest") return { result: FX.byUrl[u + " eth_getBlockByNumber " + JSON.stringify(["finalized", false])] };
    return null;
  } });
  res.check_latest_fallback_labelled = lat.pin() === ETH_PIN.replace(" · finalized", " · latest (a provider did not serve the finalized tag)")
    && lat.log.some((x) => x.m === "eth_getBlockByNumber" && x.p[0] === "latest");

  // 12. throttle: the 11th check inside a minute makes zero RPC calls
  const th = page();
  let thOk = true;
  for (let i = 0; i < 10; i++) { await th.submit("ethereum", FX.cases.eoa_dead.address); thOk = thOk && th.st().textContent.indexOf("Done:") === 0; }
  const before = th.log.length;
  await th.submit("ethereum", FX.cases.eoa_dead.address);
  res.check_throttle_11th = thOk && th.log.length === before && th.st().hasAttribute("data-ck-throttled")
    && /^Up to 10 checks a minute, so the public RPCs stay usable for everyone\. Try again in \d+ seconds\.$/.test(th.st().textContent);

  // 13. watch CTA, query-param prefill, example chips, RPC disclosure toggle, cast commands, no X tag
  const cta = maple.watch();
  const w = run(input.watch || input.check, input.app, { path: "/watch/", search: cta ? cta.replace(/^\.\.\/watch\//, "") : "" });
  const wCount = w.document.querySelector("[data-watch-count]");
  res.check_watch_cta = cta === "../watch/?chain=ethereum&address=0xbe10adce8b6e3e02db384e7fada5395dd113d8b3"
    && (maple.out().querySelector("[data-ck-watch]") || {}).textContent === "Tell me when this changes" && !!input.watch && !!wCount
    && wCount.textContent.indexOf("Selected: 1 / ") === 0 && w.document.getElementById("watch-chain").value === "ethereum";
  const q = page({ search: "?chain=base&address=" + FX.cases.usdc_base.address });
  await q.settle();
  const shown = (pg) => pg.d.querySelectorAll("[data-ck-rpcs]").filter((x) => !x.hidden).map((x) => x.getAttribute("data-ck-rpcs"));
  res.check_query_prefill = q.d.getElementById("ck-chain").value === "base" && q.d.getElementById("ck-address").value === FX.cases.usdc_base.address
    && q.pin() === BASE_PIN && same(shown(q), ["base"]);
  const ex = page();
  const chips = ex.d.querySelectorAll("[data-ck-example]");
  const s0 = same(shown(ex), ["ethereum"]);
  const tl = chips.find((b) => b.getAttribute("data-address") === FX.cases.ethena_timelock.address);
  click(tl); await ex.settle();
  res.check_examples_chips = chips.length === 4 && s0 && !!tl && has(ex.rows(), "This address", "TimelockController")
    && same(chips.map((b) => b.getAttribute("data-chain")), ["base", "ethereum", "ethereum", "ethereum"]);
  const chainSel = ex.d.getElementById("ck-chain"); chainSel.value = "base"; const cev = new Event_("change"); cev.target = chainSel; chainSel.dispatchEvent(cev);
  res.check_rpc_disclosure_toggle = same(shown(ex), ["base"])
    && ex.d.querySelector('[data-ck-rpcs="base"]').textContent === "The address you paste goes directly from your browser to these two public RPC providers (mainnet.base.org and base-rpc.publicnode.com) to read live chain state.";
  const mc = maple.cast();
  res.check_cast_commands = mc.includes("cast block 26491866 --field hash --rpc-url https://ethereum-rpc.publicnode.com")
    && mc.includes("# expect 0x77fbf13ed7493d7a6c784fc3d43481763952f365f653cd9c948ab20dfe0f0533")
    && mc.includes("cast storage 0xbe10adce8b6e3e02db384e7fada5395dd113d8b3 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --block 26491866")
    && !!maple.out().querySelector("[data-copy-term]");
  const prod = page({ hostname: "pacta.wtf" });
  res.check_no_x_tag = prod.d.querySelectorAll('script[src="https://static.ads-twitter.com/uwt.js"]').length === 0 && same(prod.p.window.__pactaTwqEvents || [], []);


  // 15. Round-1 verifier counterexamples (CK-01 .. CK-08), each a synthetic answer built from the recorded fixtures, plus edge cases.
  //     The first part is the verifier's own probe set, kept as written; the assertions below require every defect to be gone.
  const independent = {};
  const snapshot = pg => ({status:pg.st().textContent, pin:pg.pin(), rows:pg.rows(), latestRequests:pg.log.filter(x=>x.m==='eth_getBlockByNumber'&&x.p[0]==='latest').length, misses:pg.misses, text:pg.out().textContent});
  const finalizedRecord = u => FX.byUrl[u + ' eth_getBlockByNumber ' + JSON.stringify(['finalized',false])];
  independent.internal_error_fallback = snapshot(await live('ethena_timelock',{tamper:(u,m,p)=>m==='eth_getBlockByNumber'?(p[0]==='finalized'?{error:{code:-32603,message:'internal server error'}}:p[0]==='latest'?{result:finalizedRecord(u)}:null):null}));
  independent.null_code = snapshot(await live('maple_ppm',{tamper:(u,m)=>m==='eth_getCode'?{result:null}:null}));
  independent.invalid_code = snapshot(await live('maple_ppm',{tamper:(u,m)=>m==='eth_getCode'?{result:'0xzz'}:null}));
  independent.null_slots = snapshot(await live('maple_ppm',{tamper:(u,m)=>m==='eth_getStorageAt'?{result:null}:null}));
  independent.null_guard = snapshot(await live('inverse_policy_safe',{tamper:(u,m,p)=>m==='eth_getStorageAt'&&p[1]==='0x4a204f620c8c5ccdca3fd54d003badd85ba500436a431f0cbda4f558c93c34c8'?{result:null}:null}));
  function firstTarget(data) {let h=data.slice(10), base=Number(BigInt('0x'+h.slice(0,64)))*2+64, rel=Number(BigInt('0x'+h.slice(base,base+64)))*2;return '0x'+h.slice(base+rel+24,base+rel+64);}
  const mapleTarget=FX.cases.maple_ppm.address.toLowerCase();
  independent.controller_error = snapshot(await live('maple_ppm',{tamper:(u,m,p)=>m==='eth_call'&&firstTarget(p[0].data)!==mapleTarget?{error:{code:-32603,message:'controller reads failed'}}:null}));
  independent.controller_disagree = snapshot(await live('maple_ppm',{tamper:(u,m,p,r)=>u===B&&m==='eth_call'&&firstTarget(p[0].data)!==mapleTarget?{result:r.slice(0,-2)+(r.slice(-2)==='00'?'01':'00')}:null}));
  const vault=FX.cases.lagoon_vault.address.toLowerCase();
  independent.beacon_impl_error = snapshot(await live('lagoon_vault',{tamper:(u,m,p,r)=>m==='eth_getCode'&&p[0].toLowerCase()!==vault&&r&&r.length>1000?{error:{code:-32603,message:'implementation unavailable'}}:null}));
  independent.non_enumerable_no_grant_selector = snapshot(await live('reth',{tamper:(u,m,p)=>m==='eth_getCode'&&p[0].toLowerCase()===FX.cases.reth.address.toLowerCase()?{result:'0x6340c10f19638456cb5900'}:null}));
  independent.wrong_number_equal_hash = snapshot(await live('usdc_base',{tamper:(u,m,p,r)=>m==='eth_getBlockByNumber'&&p[0]!=='finalized'&&r?{result:{number:'0x1',hash:'0x'+'12'.repeat(32)}}:null}));
  independent.unreachable_mint = snapshot(await live('eoa_dead',{tamper:(u,m)=>m==='eth_getCode'?{result:'0x006340c10f19'}:null}));
  const word=n=>BigInt(n).toString(16).padStart(64,'0');
  const changeResult = (raw,index,data) => {
    const h=raw.slice(2), base=Number(BigInt('0x'+h.slice(0,64)))*2+64;
    const t=base+Number(BigInt('0x'+h.slice(base+index*64,base+(index+1)*64)))*2;
    const d=t+Number(BigInt('0x'+h.slice(t+64,t+128)))*2+64;
    return '0x'+h.slice(0,d)+data+h.slice(d+data.length);
  };
  independent.invalid_bool = snapshot(await live('usdc_base',{tamper:(u,m,p,r)=>m==='eth_call'&&firstTarget(p[0].data)===FX.cases.usdc_base.address.toLowerCase()?{result:changeResult(r,10,word(2))}:null}));
  const ownerConst='11'.repeat(20), implConst='22'.repeat(20);
  const retAddr=a=>'5b5073'+a+'60005260206000f3';
  let dispatcher='60003560e01c80638da5cb5b1460XX5780635c60da1b1460YY5700';
  const first=dispatcher.length/2, second=first+retAddr(ownerConst).length/2;
  const readonlyRuntime='0x'+dispatcher.replace('XX',first.toString(16).padStart(2,'0')).replace('YY',second.toString(16).padStart(2,'0'))+retAddr(ownerConst)+retAddr(implConst);
  const aggResults = rs => {let offset=rs.length*32, heads='',tails='';for(const data of rs){heads+=word(offset);const item=word(1)+word(64)+word(data.length/2)+data.padEnd(Math.ceil(data.length/64)*64,'0');tails+=item;offset+=item.length/2;}return '0x'+word(32)+word(rs.length)+heads+tails;};
  const readonlyTarget=FX.cases.eoa_dead.address.toLowerCase();
  independent.readonly_owner_implementation = snapshot(await live('eoa_dead',{tamper:(u,m,p)=>{
    if(m==='eth_getCode') return {result:p[0].toLowerCase()===readonlyTarget?readonlyRuntime:'0x'};
    if(m==='eth_getStorageAt') return {result:'0x'+word(0)};
    if(m!=='eth_call')return null;
    const h=p[0].data.slice(10),base=Number(BigInt('0x'+h.slice(0,64)))*2+64,n=Number(BigInt('0x'+h.slice(base-64,base))),rs=[];
    for(let i=0;i<n;i++) {const t=base+Number(BigInt('0x'+h.slice(base+i*64,base+(i+1)*64)))*2,target='0x'+h.slice(t+24,t+64),d=t+Number(BigInt('0x'+h.slice(t+128,t+192)))*2+64,sel=h.slice(d,d+8);rs.push(target===readonlyTarget&&sel==='8da5cb5b'?'0'.repeat(24)+ownerConst:target===readonlyTarget&&sel==='5c60da1b'?'0'.repeat(24)+implConst:'');}
    return {result:aggResults(rs)};
  }}));
  const ir_ = (k, key) => ((independent[k].rows[key] || {}).t || "");
  const INV = "could not read (invalid response)";
  const okText = (t) => !/A standard mint path is present|can point|authorized by the implementation's own logic/.test(t);
  const NOGET = "no Safe, multisig or timelock getter exposed";

  // CK-01: only a positively unsupported finalized tag moves the pin to latest
  const rl = snapshot(await live('ethena_timelock', { tamper: (u, m, p) => (m === 'eth_getBlockByNumber' && p[0] === 'finalized' ? { error: { code: -32005, message: 'rate limit exceeded' } } : null) }));
  const mixed = snapshot(await live('ethena_timelock', { tamper: (u, m, p) => (m === 'eth_getBlockByNumber' && p[0] === 'finalized'
    ? (u === B ? { error: { code: -32603, message: 'internal error' } } : { error: { code: -32602, message: 'unsupported block tag: finalized' } }) : null) }));
  const ie = independent.internal_error_fallback;
  res.check_ck01_fallback_narrow = ie.latestRequests === 0 && ie.status === "could not read (RPC error -32603)." && ie.pin === ""
    && rl.latestRequests === 0 && rl.status === "could not read (RPC rate limit)." && mixed.latestRequests === 0 && mixed.status === "could not read (RPC error -32603).";

  // CK-02: malformed answers are "could not read (invalid response)", never empty, zero or absent
  const short = snapshot(await live('maple_ppm', { tamper: (u, m) => (m === 'eth_getStorageAt' ? { result: '0x1234' } : null) }));
  const zero0 = snapshot(await live('maple_ppm', { tamper: (u, m) => (m === 'eth_getCode' ? { result: '0x0' } : null) }));
  const hiPad = snapshot(await live('maple_ppm', { tamper: (u, m, p, r) => (m === 'eth_call' && firstTarget(p[0].data) === mapleTarget
    ? { result: changeResult(r, 1, 'ff' + changeResultWord(r, 1).slice(2)) } : null) }));
  function changeResultWord(raw, index) {   // the current 32-byte return word of call `index`
    const h = raw.slice(2), base = Number(BigInt('0x' + h.slice(0, 64))) * 2 + 64;
    const t = base + Number(BigInt('0x' + h.slice(base + index * 64, base + (index + 1) * 64))) * 2;
    const d = t + Number(BigInt('0x' + h.slice(t + 64, t + 128))) * 2 + 64;
    return h.slice(d, d + 64);
  }
  const aggBool = snapshot(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' && firstTarget(p[0].data) === FX.cases.usdc_base.address.toLowerCase()
    ? { result: (() => { const h = r.slice(2), base = Number(BigInt('0x' + h.slice(0, 64))) * 2 + 64, t = base + Number(BigInt('0x' + h.slice(base, base + 64))) * 2;
        return '0x' + h.slice(0, t) + word(2) + h.slice(t + 64); })() } : null) }));
  const badBlock = snapshot(await live('ethena_timelock', { tamper: (u, m, p, r) => (m === 'eth_getBlockByNumber' && r ? { result: { number: '0x0' + r.number.slice(2), hash: r.hash } } : null) }));
  const ns = independent.null_slots;
  res.check_ck02_malformed_not_empty = ir_('null_code', 'eth_getCode') === INV && ir_('invalid_code', 'eth_getCode') === INV
    && (zero0.rows.eth_getCode || {}).t === INV
    && ["EIP-1967 implementation slot", "EIP-1967 admin slot", "EIP-1967 beacon slot", "EIP-1822 PROXIABLE slot", "ZeppelinOS implementation slot", "ZeppelinOS admin slot"]
      .every((k) => ir_('null_slots', k) === INV && (short.rows[k] || {}).t === INV)
    && !/No proxy slot|No standard proxy slot/.test(ns.text + short.text) && ir_('null_slots', 'Upgrade admin') === INV
    && ir_('null_slots', 'Upgrade proxy').indexOf("Not every proxy slot could be read") === 0
    && ir_('null_guard', 'This address').includes("Safe guard " + INV) && !ir_('null_guard', 'This address').includes("no Safe guard")
    && ir_('invalid_bool', 'paused()') === INV && (hiPad.rows['admin()'] || {}).t === INV
    && ["owner()", "paused()", "totalSupply()", "pauser()"].every((k) => (aggBool.rows[k] || {}).t === INV)
    && badBlock.status === "could not read (invalid response)." && badBlock.pin === "";

  // CK-03: a controller whose probes failed or disagreed shows that, never "no Safe, multisig or timelock getter exposed"
  const selfDis = snapshot(await live('ethena_timelock', { tamper: (u, m, p, r) => (u === B && m === 'eth_call' ? { result: r.slice(0, -2) + (r.slice(-2) === '00' ? '01' : '00') } : null) }));
  res.check_ck03_controller_failures_shown = ir_('controller_error', 'Upgrade admin').includes("could not read (RPC error -32603)")
    && ir_('controller_disagree', 'Upgrade admin').includes(DIS)
    && ["Upgrade admin", "admin()"].every((k) => !ir_('controller_error', k).includes(NOGET) && !ir_('controller_disagree', k).includes(NOGET))
    && ir_('controller_disagree', 'admin()').includes(DIS) && (selfDis.rows['This address'] || {}).t === "contract (0xe8dc…7c94) · getThreshold() " + DIS
    && (selfDis.rows['Can supply grow?'] || {}).t === "comptrollerImplementation() " + DIS;

  // CK-04: an unread beacon implementation (its code, or implementation() itself) blocks every selector conclusion
  const bimpl = snapshot(await live('lagoon_vault', { tamper: (u, m, p) => (m === 'eth_call' && firstTarget(p[0].data) === '0x707d622cda4b5459e7dcee8ba8e429f154f96a27'
    ? { error: { code: -32603, message: 'beacon reads failed' } } : null) }));
  const BIC = "beacon implementation code could not read (RPC error -32603)", BIF = "beacon implementation() could not read (RPC error -32603)";
  res.check_ck04_beacon_unread = ir_('beacon_impl_error', 'pause() in bytecode') === BIC && ir_('beacon_impl_error', 'Mint functions in bytecode') === BIC
    && ir_('beacon_impl_error', 'Can supply grow?') === BIC && ir_('beacon_impl_error', 'Pause role holders') === BIC && ir_('beacon_impl_error', 'Mint role holders') === BIC
    && (bimpl.rows['pause() in bytecode'] || {}).t === BIF && (bimpl.rows['Beacon implementation()'] || {}).t === "could not read (RPC error -32603)"
    && !/no pause\(\) selector|none of mint|no standard mint getter/.test(independent.beacon_impl_error.text + bimpl.text);

  // CK-05: the pinned hash is bound to the requested height on both providers
  const numSplit = snapshot(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_getBlockByNumber' && p[0] !== 'finalized' && r && u === URLS.base[1] ? { result: { number: '0x3b31910', hash: r.hash } } : null) }));
  const wn = independent.wrong_number_equal_hash;
  res.check_ck05_block_number_bound = wn.status === "could not read (RPC block number mismatch)." && wn.pin === "" && !wn.text.includes("0x1212")
    && numSplit.status === DIS + "." && numSplit.pin === "";

  // CK-06: pause / mint holders that cannot be listed are "not determined", with or without a grantRole selector
  const ne = independent.non_enumerable_no_grant_selector;
  res.check_ck06_roles_not_determined = ir_('non_enumerable_no_grant_selector', 'Pause role holders') === "not determined"
    && ir_('non_enumerable_no_grant_selector', 'Mint role holders') === "not determined" && ne.misses.length === 0;

  // CK-07: a selector in the bytes is an observation; capability is not determined
  res.check_ck07_selector_not_capability = ir_('unreachable_mint', 'Mint functions in bytecode') === "selector observed in bytecode: mint(address,uint256)"
    && ir_('unreachable_mint', 'Can supply grow?') === "not determined from static bytecode and getter reads alone. Observed: a mint selector was observed in the bytecode."
    && okText(independent.unreachable_mint.text);

  // CK-08: getter answers are addresses, never proof of who can upgrade
  res.check_ck08_no_upgrade_authority_claims = ir_('readonly_owner_implementation', 'Who can upgrade').indexOf("not determined from getter reads alone") === 0
    && Object.values(independent).every((x) => okText(x.text)) && [lb, lv, usual, maple, usdc, reth].every((pg) => okText(pg.out().textContent))
    && has(lv.rows(), "Upgrade admin", "not determined");

  // 15b. round-2 verifier edge cases (CKR2-01..06): adjacent inputs to the round-1 fixes, replayed on recorded answers
  {
    const snap = (pg) => ({ status: pg.st().textContent, pin: pg.pin(), rows: pg.rows(), text: pg.out().textContent,
      latestRequests: pg.log.filter((x) => x.m === 'eth_getBlockByNumber' && x.p[0] === 'latest').length });
    const row = (x, k) => ((x.rows[k] || {}).t || "");
    const w = (n) => BigInt(n).toString(16).padStart(64, '0');
    const decodeRet = (raw) => { const h = raw.slice(2), base = Number(BigInt('0x' + h.slice(0, 64))) * 2 + 64, n = Number(BigInt('0x' + h.slice(base - 64, base))), a = [];
      for (let i = 0; i < n; i++) { const t = base + Number(BigInt('0x' + h.slice(base + i * 64, base + (i + 1) * 64))) * 2, d = t + Number(BigInt('0x' + h.slice(t + 64, t + 128))) * 2,
        len = Number(BigInt('0x' + h.slice(d, d + 64))) * 2; a.push({ success: h.slice(t, t + 64) === w(1), data: h.slice(d + 64, d + 64 + len) }); } return a; };
    const encodeRet = (rs) => { let off = rs.length * 32, heads = '', tails = '';
      for (const r of rs) { heads += w(off); const t = w(r.success ? 1 : 0) + w(64) + w(r.data.length / 2) + r.data.padEnd(Math.ceil(r.data.length / 64) * 64, '0'); off += t.length / 2; tails += t; }
      return '0x' + w(32) + w(rs.length) + heads + tails; };
    const callTargets = (data) => { const h = data.slice(10), base = Number(BigInt('0x' + h.slice(0, 64))) * 2 + 64, n = Number(BigInt('0x' + h.slice(base - 64, base))), a = [];
      for (let i = 0; i < n; i++) { const t = base + Number(BigInt('0x' + h.slice(base + i * 64, base + (i + 1) * 64))) * 2, d = t + Number(BigInt('0x' + h.slice(t + 128, t + 192))) * 2 + 64;
        a.push({ target: '0x' + h.slice(t + 24, t + 64), sel: h.slice(d, d + 8), data: h.slice(d, d + Number(BigInt('0x' + h.slice(d - 64, d))) * 2) }); } return a; };
    const atoms = new Map();
    for (const [key, raw] of Object.entries(FX.byChain)) { const mt = key.match(/^(\w+) eth_call (.*)$/); if (!mt) continue;
      const params = JSON.parse(mt[2]), cs = callTargets(params[0].data), rs = decodeRet(raw); cs.forEach((c, i) => atoms.set(mt[1] + ' ' + params[1] + ' ' + c.target + ' ' + c.data, rs[i])); }
    const recombine = (p) => { const rs = callTargets(p[0].data).map((c) => atoms.get('ethereum ' + p[1] + ' ' + c.target + ' ' + c.data)); if (rs.some((x) => !x)) throw Error('missing atomic fixture'); return encodeRet(rs); };
    const edit = (p, r, selector, value) => { const cs = callTargets(p[0].data), rs = decodeRet(r); cs.forEach((c, i) => { if (c.sel === selector) rs[i] = value; }); return encodeRet(rs); };
    const fin = (u) => FX.byUrl[u + ' eth_getBlockByNumber ' + JSON.stringify(['finalized', false])];
    const tagErr = (code, message, latestToo) => ({ tamper: (u, m, p) => (m === 'eth_getBlockByNumber' ? (p[0] === 'finalized' ? { error: { code, message } } : p[0] === 'latest' ? { result: fin(u) } : null) : null) });
    const edge = {};
    // CKR2-01: missing block data never selects "latest"; only an explicit tag / parameter rejection does
    const NEG = [[-32001, 'finalized block not found'], [-32000, 'unknown block number'], [-32000, 'finalized unavailable'], [-32000, 'header not found'],
      [-32602, 'missing finalized block'], [-32603, 'internal error'], [-32005, 'rate limit exceeded'], [-32000, 'block number too high']];
    const POS = [[-32602, 'invalid block tag finalized'], [-32602, 'unsupported block tag: finalized'], [-32000, 'invalid block tag'],
      [-32602, 'invalid argument 0: hex string without 0x prefix: finalized'], [-32601, 'unknown block tag']];
    for (const [c, msg] of NEG) edge['neg ' + msg] = snap(await live('ethena_timelock', tagErr(c, msg)));
    for (const [c, msg] of POS) edge['pos ' + msg] = snap(await live('ethena_timelock', tagErr(c, msg)));
    const LATEST = ETH_PIN.replace(" · finalized", " · latest (a provider did not serve the finalized tag)");
    res.check_ckr2_01_tag_fallback_explicit_only = NEG.every(([c, msg]) => edge['neg ' + msg].latestRequests === 0 && edge['neg ' + msg].pin === ""
        && edge['neg ' + msg].status === "could not read (" + (c === -32005 ? "RPC rate limit" : "RPC error " + c) + ").")
      && POS.every(([c, msg]) => edge['pos ' + msg].latestRequests === 2 && edge['pos ' + msg].pin === LATEST);
    // CKR2-02: each controller getter is decoded with its own type before any conclusion; defaultAdminDelay() failures are shown
    edge.owners_malformed = snap(await live('reth', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, 'a0e67e2b', { success: true, data: '01' }) } : null) }));
    edge.dad_malformed = snap(await live('usual_registry_access', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, 'cc8463c8', { success: true, data: '01' }) } : null) }));
    const typedBad = [['e75235b8', 'getThreshold', '01'], ['dc8452cd', 'required', '01'], ['f27a0c92', 'getMinDelay', '01'], ['31d50750', 'isOperation', w(2)],
      ['6a42b8f8', 'delay', '01'], ['8da5cb5b', 'owner', '01' + w(1)], ['5c60da1b', 'implementation', w(1).replace(/^00/, 'ff')]];
    for (const [sel, name, data] of typedBad) edge['typed ' + name] = snap(await live('reth', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, sel, { success: true, data }) } : null) }));
    res.check_ckr2_02_malformed_getters_shown = row(edge.owners_malformed, 'This address') === "contract (0xae78…6393) · getOwners() " + INV
      && !edge.owners_malformed.text.includes(NOGET) && row(edge.dad_malformed, 'defaultAdminDelay()') === INV
      && typedBad.every(([, name]) => row(edge['typed ' + name], 'This address') === "contract (0xae78…6393) · " + name + "() " + INV && !edge['typed ' + name].text.includes(NOGET));
    // CKR2-03: an unreadable / non-address proxy or beacon slot, or a failed comptrollerImplementation(), blocks selector conclusions
    const slotErr = (c, slot) => live(c, { tamper: (u, m, p) => (m === 'eth_getStorageAt' && p[1] === slot ? { error: { code: -32603, message: 'read failed' } }
      : c === 'lagoon_vault' && m === 'eth_call' ? { result: recombine(p) } : null) });
    edge.beacon_slot = snap(await slotErr('lagoon_vault', '0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50'));
    edge.zos_slot = snap(await slotErr('usdc_base', '0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3'));
    edge.zos_odd = snap(await live('usdc_base', { tamper: (u, m, p) => (m === 'eth_getStorageAt' && p[1] === '0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3' ? { result: '0x' + 'f'.repeat(64) } : null) }));
    edge.cimpl = snap(await live('maple_ppm', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, 'bb82aa5e', { success: true, data: '01' }) } : null) }));
    const BEA = "EIP-1967 beacon slot could not read (RPC error -32603)", ZOS = "ZeppelinOS implementation slot could not read (RPC error -32603)";
    const DEP = ['pause() in bytecode', 'Mint functions in bytecode', 'Can supply grow?', 'Pause role holders', 'Mint role holders'];
    const leads = (x, t) => DEP.every((k) => row(x, k).indexOf(t) === 0 || row(x, k).indexOf("selector observed in bytecode: ") === 0 && row(x, k).endsWith(" (" + t + ")"));
    res.check_ckr2_03_discovery_failures_unread = leads(edge.beacon_slot, BEA) && row(edge.beacon_slot, 'pause() in bytecode') === BEA && leads(edge.zos_slot, ZOS)
      && row(edge.zos_slot, 'Can supply grow?') === ZOS + " (observed: masterMinter() returned an address)"
      && leads(edge.zos_odd, "ZeppelinOS implementation slot holds a value that is not an address")
      && ['pause() in bytecode', 'Mint functions in bytecode', 'Can supply grow?'].every((k) => row(edge.cimpl, k).indexOf("comptrollerImplementation() " + INV) === 0)
      && [edge.beacon_slot, edge.zos_slot, edge.zos_odd, edge.cimpl].every((x) => !/no pause\(\) selector observed|none of mint/.test(x.text));
    // CKR2-04: without a usable decimals(), supply values are raw integer units and never carry the symbol as if scaled
    edge.dec_malformed = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '313ce567', { success: true, data: '01' }) } : null) }));
    edge.dec_reverted = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '313ce567', { success: false, data: '' }) } : null) }));
    edge.dec_huge = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '313ce567', { success: true, data: w(37) }) } : null) }));
    edge.sym_malformed = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '95d89b41', { success: true, data: '01' }) } : null) }));
    edge.cap_raw = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, edit(p, r, '313ce567', { success: false, data: '' }), '355274ea', { success: true, data: w(1000) }) } : null) }));
    const RAW = "raw 4,283,493,874,807,210 (decimals() ";
    res.check_ckr2_04_raw_units_without_decimals = row(edge.dec_malformed, 'totalSupply()') === RAW + INV + "; token amount not determined; symbol() USDC)"
      && row(edge.dec_reverted, 'totalSupply()') === RAW + ABS + "; token amount not determined; symbol() USDC)"
      && row(edge.dec_huge, 'totalSupply()') === RAW + "37 > 36; token amount not determined; symbol() USDC)"
      && row(edge.sym_malformed, 'totalSupply()') === "4,283,493,874.80721 (raw 4,283,493,874,807,210, 6 decimals; symbol() " + INV + ")"
      && row(edge.cap_raw, 'cap()') === "raw 1,000 (decimals() " + ABS + "; token amount not determined; symbol() USDC)"
      && [edge.dec_malformed, edge.dec_reverted, edge.dec_huge, edge.cap_raw].every((x) => !/[0-9] USDC/.test(x.text));
    // CKR2-05: a single pauser() / masterMinter() getter never hides the role-holder rows
    edge.single_getter = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_getCode' ? { result: r.replaceAll('632f2ff15d', '6301020304') } : null) }));
    res.check_ckr2_05_single_getter_not_suppressed = ['Pause role holders', 'Mint role holders'].every((k) => row(edge.single_getter, k) === "not determined")
      && ['Pause role holders', 'Mint role holders'].every((k) => (usdc.rows()[k] || {}).t === "not determined");
    // CKR2-06: two different answers disagree before either is judged malformed; the same malformed answer is "invalid response"
    edge.code_null_b = snap(await live('maple_ppm', { tamper: (u, m) => (u === B && m === 'eth_getCode' ? { result: null } : null) }));
    edge.code_bad_b = snap(await live('maple_ppm', { tamper: (u, m) => (u === B && m === 'eth_getCode' ? { result: '0xgg' } : null) }));
    edge.code_null_both = snap(await live('maple_ppm', { tamper: (u, m) => (m === 'eth_getCode' ? { result: null } : null) }));
    edge.slot_short_b = snap(await live('maple_ppm', { tamper: (u, m) => (u === B && m === 'eth_getStorageAt' ? { result: '0x1234' } : null) }));
    edge.call_null_b = snap(await live('maple_ppm', { tamper: (u, m) => (u === B && m === 'eth_call' ? { result: null } : null) }));
    const blk = (fn) => live('ethena_timelock', { tamper: (u, m, p) => (m === 'eth_getBlockByNumber' ? fn(u, p) : null) });
    edge.blk_null_b = snap(await blk((u, p) => (u === B && p[0] === 'finalized' ? { result: null } : null)));
    edge.blk_bad_b = snap(await blk((u, p) => (u === B && p[0] === 'finalized' ? { result: { number: '0x00', hash: fin(u).hash } } : null)));
    edge.blk_null_both = snap(await blk((u, p) => (p[0] === 'finalized' ? { result: null } : null)));
    edge.blk_bad_both = snap(await blk((u, p) => (p[0] === 'finalized' ? { result: { number: '0x00', hash: fin(u).hash } } : null)));
    const up1 = (u) => ({ number: '0x' + (BigInt(fin(u).number) + 1n).toString(16), hash: '0x' + 'ab'.repeat(32) });
    edge.requery_null_b = snap(await blk((u, p) => (p[0] === 'finalized' ? { result: u === B ? up1(u) : fin(u) } : /^0x/.test(p[0]) ? { result: u === B ? null : fin(u) } : null)));
    edge.requery_null_both = snap(await blk((u, p) => (p[0] === 'finalized' ? { result: u === B ? up1(u) : fin(u) } : /^0x/.test(p[0]) ? { result: null } : null)));
    res.check_ckr2_06_disagreement_before_shape = row(edge.code_null_b, 'eth_getCode') === DIS && row(edge.code_bad_b, 'eth_getCode') === DIS
      && row(edge.code_null_both, 'eth_getCode') === INV && row(edge.slot_short_b, 'Upgrade admin') === DIS && row(edge.call_null_b, 'owner()') === DIS
      && [edge.blk_null_b, edge.blk_bad_b, edge.requery_null_b].every((x) => x.status === DIS + "." && x.pin === "")
      && edge.blk_null_both.status === "could not read (RPC returned no block)." && edge.blk_bad_both.status === "could not read (invalid response)."
      && edge.requery_null_both.status === "could not read (RPC returned no block)." && Object.values(edge).every((x) => okText(x.text));
    // canonical ABI only: aggregate3 tuples whose offsets alias the heads (or each other) are malformed, never decoded
    edge.aliased = snap(await live('maple_ppm', { tamper: (u, m, p) => { if (m !== 'eth_call') return null; const n = callTargets(p[0].data).length;
      return { result: '0x' + w(32) + w(n) + Array.from({ length: n }, (_, i) => w(n * 32 + i * 64)).join('') + (w(0) + w(0)).repeat(n) }; } }));
    edge.trailing = snap(await live('maple_ppm', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: r + w(0) } : null) }));
    edge.shared = snap(await live('maple_ppm', { tamper: (u, m, p, r) => { if (m !== 'eth_call') return null;
      const h = r.slice(2), n = Number(BigInt('0x' + h.slice(64, 128))); if (n < 2) return null;   // tuple 1 re-uses tuple 0's offset
      return { result: '0x' + h.slice(0, 192) + h.slice(128, 192) + h.slice(256) }; } }));
    // the top-level array offset must be 0x20 (no zero-word gap), and every bytes / string must be right-padded with zeros only
    edge.gap40 = snap(await live('maple_ppm', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: '0x' + w(64) + w(0) + r.slice(66) } : null) }));
    edge.gap60 = snap(await live('maple_ppm', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: '0x' + w(96) + w(0) + w(0) + r.slice(66) } : null) }));
    const USDC_SYM = w(32) + w(4) + '55534443';   // "USDC", 68 bytes before padding
    edge.pad_ff = snap(await live('usdc_base', { tamper: (u, m, p, r) => { if (m !== 'eth_call') return null;
      const x = edit(p, r, '95d89b41', { success: true, data: USDC_SYM }), at = x.indexOf(USDC_SYM + '0'.repeat(56));
      return at < 0 ? null : { result: x.slice(0, at + USDC_SYM.length + 54) + 'ff' + x.slice(at + USDC_SYM.length + 56) }; } }));
    edge.str_gap = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '95d89b41', { success: true, data: w(64) + w(0) + w(4) + '55534443' + '0'.repeat(56) }) } : null) }));
    edge.str_off = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '95d89b41', { success: true, data: w(64) + w(4) + '55534443' + '0'.repeat(56) }) } : null) }));
    edge.str_pad = snap(await live('usdc_base', { tamper: (u, m, p, r) => (m === 'eth_call' ? { result: edit(p, r, '95d89b41', { success: true, data: USDC_SYM + '0'.repeat(54) + 'ff' }) } : null) }));
    const SYM_BAD = "4,283,493,874.80721 (raw 4,283,493,874,807,210, 6 decimals; symbol() " + INV + ")";
    res.check_ckr2_aggregate_canonical = [edge.aliased, edge.trailing, edge.shared, edge.gap40, edge.gap60].every((x) => ['owner()', 'admin()', 'paused()', 'totalSupply()'].every((k) => row(x, k) === INV)
      && row(x, 'This address').endsWith("() " + INV) && !x.text.includes(NOGET))
      && ['owner()', 'paused()', 'totalSupply()'].every((k) => row(edge.pad_ff, k) === INV)
      && [edge.str_gap, edge.str_off, edge.str_pad].every((x) => row(x, 'totalSupply()') === SYM_BAD);
  }

  // 14. the words gate over every rendered result (and a self-test that it bites)
  res.check_words_gate = gateSelf && gateBad.length === 0;
  if (gateBad.length) res.check_words_bad = gateBad.slice(0, 4);
  // only the four public RPCs are ever contacted, by POST, and never the Pacta API or a beacon
  res.check_only_public_rpcs = [maple, usual, eth, lb, lv, usdc, reth, inv, eoa, q, ex, th].every((pg) => pg.log.every((x) => !!chainOf(x.u)) && pg.p.beacons.length === 0);
}
(async () => {
  try { await v45Scenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await pfComboboxScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await internalQaScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await walletExposureScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await requestBriefScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await requestNotStoredScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
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
  try { await watchScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await xPixelScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await miniAppScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await miniAppResetScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await liveTimelockScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await lateLivePayloadScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await basePathScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await visitorScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await liveRpcScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  try { await checkScenario(); } catch (e) { res.harness_error = (res.harness_error || "") + String(e && e.stack || e); }
  res.v43_no_init_errors = INIT_ERRORS.length === 0;
  if (INIT_ERRORS.length) res.init_errors = INIT_ERRORS.slice(0, 3);
  process.stdout.write(JSON.stringify(res));
})();
