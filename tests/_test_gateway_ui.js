/* The panel has to work when fnOS opens it, and on a phone.
 *
 * Three things only a browser would otherwise notice, all of them silent
 * failures on the server:
 *
 *   * every API call is built through wbUrl(), because behind the App Center
 *     the page is served from /app/workbuddy2api/ and a root-absolute fetch
 *     would leave the panel and 404;
 *   * the password gate knows how the visitor arrived - a port visit gets the
 *     "open it from fnOS" card, a gateway visit without a signed-in user gets
 *     the password box;
 *   * the palette is a real theme, so the dark setting is not just a class
 *     nobody styles.
 *
 * It drives the shipped dashboard.html with a stub DOM, the same way
 * _test_realm_view.js does. Run with Node.
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'dashboard.html'), 'utf8');
const style = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

// ---------------------------------------------------------------- stub DOM
const elements = Object.create(null);
function make(id) {
  return {
    id, innerHTML: '', textContent: '', value: '', title: '', className: '',
    style: {}, attrs: {}, focused: false,
    classList: {add() {}, remove() {}, contains() { return false; }},
    addEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; },
    appendChild() {}, remove() {}, focus() { this.focused = true; },
    setAttribute(k, v) { this.attrs[k] = v; }, getAttribute(k) { return this.attrs[k] || ''; },
  };
}
const el = id => (elements[id] || (elements[id] = make(id)));
const meta = make('theme-color-meta');

const store = {};
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.sessionStorage = global.localStorage;
global.document = {
  getElementById: el,
  querySelector: sel => (sel.indexOf('theme-color') !== -1 ? meta : null),
  querySelectorAll: () => [],
  addEventListener() {},
  createElement: () => make('created'),
  body: el('body'), head: el('head'),
  documentElement: el('html'),
};
let systemDark = false;
// One persistent MediaQueryList, like a browser: it keeps answering the same
// object while the preference changes underneath it.
const darkQuery = {get matches() { return systemDark; }, addEventListener() {}};
global.window = {
  addEventListener() {}, location: {href: '', search: ''},
  matchMedia: () => darkQuery,
};
global.navigator = {userAgent: 'node'};
global.location = {href: '', search: '', hash: '', hostname: 'nas.local',
                 protocol: 'http:', origin: 'http://nas.local:5666'};
global.setInterval = () => 0;
global.setTimeout = () => 0;
global.alert = () => {};
global.confirm = () => false;
global.fetch = () => Promise.resolve({
  status: 200, ok: true,
  json: () => Promise.resolve({accounts: [], data: [], current: 'intl', results: []}),
  text: () => Promise.resolve('{}'),
});

const api = new Function(scripts + `
  return {wbUrl, setGateMode, panelNeedsLogin, showPasswordLogin, cycleTheme,
          fmtTok, modelRate, renderUsageNotes,
          theme: window.__WB_THEME__,
          base: v => { window.__WB_BASE__ = v; },
          setPanelStatus: v => { PANEL_STATUS = v; }};
`)();

const htmlAttr = name => elements.html.attrs[name];
const metaColor = () => meta.attrs.content;

// ------------------------------------------------------- API-URL prefixes
assert.strictEqual(api.wbUrl('/health'), '/health',
  'a direct visit keeps root-absolute paths');
assert.strictEqual(api.wbUrl('health'), 'health',
  'a relative path is none of wbUrl\'s business');
assert.strictEqual(api.wbUrl(undefined), undefined, 'wbUrl passes non-strings through');

api.base('/app/workbuddy2api');
assert.strictEqual(api.wbUrl('/panel/status'), '/app/workbuddy2api/panel/status',
  'behind the gateway every API path has to carry the prefix');
api.base('/app/workbuddy2api/');
assert.strictEqual(api.wbUrl('/accounts'), '/app/workbuddy2api/accounts',
  'a trailing slash in the injected base must not double up');
assert.strictEqual(api.wbUrl('/accounts/export') + '?kind=cn',
  '/app/workbuddy2api/accounts/export?kind=cn',
  'the export URL is built the same way the helpers build theirs');
api.base('');

// Nothing may fetch a root-absolute path directly: those calls bypass the
// prefix and work only when the panel happens to be served from the root.
const bareFetch = [...scripts.matchAll(/fetch\(\s*(['"])/g)];
assert.deepStrictEqual(bareFetch, [],
  'a fetch() with a literal URL ignores the gateway prefix');

// ------------------------------------------------------------- the gate
api.setPanelStatus({});
api.panelNeedsLogin();
assert.strictEqual(el('panelGate').style.display, 'flex', 'the gate covers the panel');
assert.strictEqual(el('gateDirect').style.display, 'block',
  'a port visit is told to open the panel from fnOS');
assert.strictEqual(el('gatePassword').style.display, 'none',
  'a port visit is not asked for a password first');

api.setPanelStatus({via_gateway: true});
api.panelNeedsLogin();
assert.strictEqual(el('gateDirect').style.display, 'none',
  'behind the gateway the fnOS advice would be wrong');
assert.strictEqual(el('gatePassword').style.display, 'block',
  'a gateway request without a signed-in user falls back to the password');

api.setGateMode('direct');
api.showPasswordLogin();
assert.strictEqual(el('gatePassword').style.display, 'block',
  'the emergency "still want the password" button has to work');
assert.strictEqual(el('panelPwdInput').focused, true, 'and focus the field');
assert.ok(/id="gateDirect"/.test(html) && /id="gatePassword"/.test(html),
  'both gate states ship in the markup');

// ------------------------------------------------------------- the theme
assert.deepStrictEqual(Object.keys(api.theme.labels).sort(), ['auto', 'dark', 'light']);
assert.strictEqual(api.theme.mode, 'auto', 'a fresh browser follows the system');
assert.strictEqual(htmlAttr('data-theme'), 'light', 'system light paints light');
assert.strictEqual(metaColor(), '#f8fafc', 'and the browser chrome follows');

assert.strictEqual(api.theme.cycle(), 'light', 'auto -> light');
assert.strictEqual(store['wb-proxy-theme'], 'light', 'the choice is remembered');
assert.strictEqual(htmlAttr('data-theme'), 'light');

assert.strictEqual(api.theme.cycle(), 'dark', 'light -> dark');
assert.strictEqual(htmlAttr('data-theme'), 'dark', 'a manual dark paints dark');
assert.strictEqual(metaColor(), '#0b1220', 'including the address bar');

systemDark = true;
assert.strictEqual(api.theme.cycle(), 'auto', 'dark -> auto');
assert.strictEqual(htmlAttr('data-theme'), 'dark', 'auto reads the system now');

assert.ok(/^\.toast-item/.test(style.replace(/\s/g, '')) || /\.toast-item\{/.test(style),
  'toasts are styled by the palette, not by inline colours');
assert.ok(html.indexOf('max-width:380px') === -1,
  'the toast width is no longer hard-coded in the script');

// --------------------------------------------------------- the mobile page
['860', '640', '400'].forEach(width => {
  assert.ok(html.indexOf('@media (max-width: ' + width + 'px)') !== -1,
    'the ' + width + 'px breakpoint is still there');
});
const phone = html.slice(html.indexOf('@media (max-width: 640px)'));
assert.ok(/input:not\(\[type=checkbox\]\):not\(\[type=radio\]\), select, textarea\{font-size:16px!important\}/.test(phone),
  'phone fields are 16px so iOS does not zoom the panel on focus');
assert.ok(/table\.data-cards tr\{display:grid/.test(phone),
  'tables still collapse into cards on a phone');
assert.ok(/viewport-fit=cover/.test(html), 'the page may paint under the notch');
assert.ok(/<meta name="theme-color"/.test(html), 'and tint the browser chrome');

// The dark palette has to override something, or the toggle is decoration.
const dark = html.slice(html.indexOf(':root[data-theme="dark"]'));
assert.ok(/--bg:#0b1220/.test(dark.slice(0, 2000)), 'the dark palette sets its own colours');
assert.ok(!/background:#fff/i.test(style), 'no surface is left hard-coded to white');
assert.ok(/:root\[data-theme="dark"\] \.badge\.ok/.test(html),
  'badges that need a readable colour in the dark get one');

// --------------------------------------------------- token units and rates
// Token counts outgrow their cell: past 10k they switch unit, and the unit
// travels with the number.
assert.strictEqual(api.fmtTok(0), '0');
assert.strictEqual(api.fmtTok(9999), '9,999', 'below 10k the exact number is readable');
assert.strictEqual(api.fmtTok(12345), '12.3 K');
assert.strictEqual(api.fmtTok(1234567), '1.23 M');
assert.strictEqual(api.fmtTok(1234567890), '1.23 B');
assert.strictEqual(api.fmtTok(3.4e12), '3.40 T');
assert.strictEqual(api.fmtTok(undefined), '0', 'a missing count prints zero, not NaN');

// 每 M tokens 多少积分, computed from the per-model credit the server now sends.
assert.strictEqual(api.modelRate(2.5, 1000000), '2.50');
assert.strictEqual(api.modelRate(1.25, 500000), '2.50', 'a rate is a ratio, not a total');
assert.strictEqual(api.modelRate(0, 1000000), '—', 'a quota-billed model has no rate');
assert.strictEqual(api.modelRate(1, 0), '—', 'no tokens means no rate, not infinity');

// The pill keeps one box per model with the rate on its second line.
assert.ok(/class="model-pill"/.test(scripts) && /mp-rate/.test(scripts),
  'the model breakdown renders the rate inside the model pill');
assert.ok(/每 M tok /.test(scripts), 'and labels it in the same unit the rate uses');

// ------------------------------------------------- addresses in 使用说明
api.setPanelStatus({direct_port: 8899});
api.renderUsageNotes();
assert.strictEqual(el('usageApi').textContent, 'http://nas.local:8899/v1',
  'the API address is the direct port the server reported');
assert.strictEqual(el('usagePanel').textContent, 'http://nas.local:8899/',
  'and so is the emergency dashboard address');
assert.strictEqual(el('usageGateway').textContent, '从应用中心 / 桌面图标打开',
  'with no prefix the page can only describe the App Center entry');
api.base('/app/workbuddy2api');
api.renderUsageNotes();
assert.strictEqual(el('usageGateway').textContent, 'http://nas.local:5666/app/workbuddy2api/',
  'opened through the gateway it prints the address this page came from');
api.base('');

// ------------------------------------------------- the console follows the theme
assert.ok(/--log-bg:#f6f8fa/.test(style), 'the light console has its own background');
assert.ok(/--log-bg:#090d16/.test(dark), 'the dark console keeps its own');
assert.ok(html.indexOf('style="height:620px;overflow-y:auto;padding:10px 12px;background:#090d16') === -1,
  'the log window paints from the palette, not from an inline black');
assert.ok(/#logTerminalBody\{[^}]*background:var\(--log-bg\)/.test(style),
  'and it is the themed variable that reaches it');
assert.ok(/tbody tr:hover\{background:var\(--row-hover\)\}/.test(style),
  'row hover is a variable, so the light wash cannot glare in the dark');
assert.ok(/--row-hover:rgba\(148,163,184,\.10\)/.test(dark),
  'the dark hover is a low-alpha film, not a lighter surface');
assert.ok(/--row-hover:rgba\(241,245,249,\.6\)/.test(style),
  'and the light theme keeps the wash it always had');

console.log('dashboard gateway/theme/mobile assertions passed (' +
  Object.keys(elements).length + ' elements stubbed)');
