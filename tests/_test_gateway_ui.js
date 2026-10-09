/* The dashboard is served two ways: directly on its own port, and from the fnOS
 * App Center, which puts it behind a mount prefix (`/app/<name>`) and a gateway
 * that has already authenticated the peer.
 *
 * The server side of that contract lives in wb_proxy.py
 * (dashboard_context_script / inject_dashboard_context): it writes
 * window.__WB_BASE__, window.__WB_VIA_GATEWAY__ and window.__WB_GATEWAY_USER__
 * into the page, plus a <base href> when there is a prefix. This suite boots the
 * shipped page twice with those globals set, and holds the page to it:
 *
 *   direct  - no prefix: requests stay site-relative, and the password gate
 *             still exists and behaves as before (that path must not regress).
 *   gateway - prefix `/app/workbuddy2api`: every request carries the prefix, and
 *             the password box is gone. Behind the gateway there is no password
 *             to ask for, and an old tab used to come back demanding one.
 *
 * It also pins the pieces a reader rather than a clicker meets: the token unit
 * formatter, the per-million-token credit column, and the mobile fallbacks.
 *
 *   node _test_gateway_ui.js
 */
'use strict';

const assert = require('assert');
const {dashboardHtml, dashboardScript} = require('./_dashboard_source.js');
const dom = require('./_dom_stub.js');

const html = dashboardHtml();
const code = dashboardScript();
const style = [...html.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
// Assertions about what the page does NOT contain have to look past the comments
// that explain why it does not contain it.
const bareHtml = html
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^[ \t]*\/\/.*$/gm, '');

let checks = 0;
let failures = 0;
async function check(label, fn) {
  try {
    await fn();
    checks++;
  } catch (err) {
    failures++;
    console.error('  [FAIL] ' + label + '\n         ' + (err && err.message));
  }
}
const eq = (actual, expected, what) =>
  assert.strictEqual(actual, expected, (what ? what + ': ' : '') + 'expected ' + JSON.stringify(expected) + ', got ' + JSON.stringify(actual));
const ok = (value, what) => assert.ok(value, what);

/* What the page script keeps in its own scope. Everything below is reached
 * through here rather than through globals, because the script is one function
 * body and only what it returns is addressable. */
const EXPORTS = `
    return {
      wbUrl, getJSON, postJSON,
      gatewayGateOff, panelNeedsLogin, panelHideGate, bootPanel, submitPanelLogin,
      helpAddresses, fillHelpAddresses, copyHelpAddress,
      fmtTok, creditPerM, fmtPerM,
      renderAvailableModels, renderPerfMatrix,
      setPanelStatus: v => { PANEL_STATUS = v; },
      getPanelStatus: () => PANEL_STATUS,
    };`;

/* Boot the real page against a fake DOM, with the mount globals the server
 * would have injected. The page touches `document`/`window` through the global
 * scope at CALL time, not at load time, so two boots must not interleave: run
 * every assertion for one boot before installing the next. */
async function boot(opts) {
  opts = opts || {};
  const calls = [];
  const routes = opts.routes || {};
  const reply = (status, body) => ({
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
  const inst = dom.installDom({
    querySelector: {'#modelsTable tbody': dom.makeElement('tbody', {permissive: true})},
    fetch: (url, options) => {
      calls.push({url: String(url), method: (options && options.method) || 'GET'});
      const body = routes[String(url)];
      if (body === null) return Promise.resolve(reply(404, {}));
      if (body && typeof body === 'object' && typeof body.status === 'number') {
        return Promise.resolve(reply(body.status, body.body === undefined ? {} : body.body));
      }
      return Promise.resolve(reply(200, body === undefined ? {} : body));
    },
  });
  const location = inst.window.location;
  if (opts.href) location.href = opts.href;
  if (opts.port) {
    location.port = opts.port;
    location.host = (opts.host || location.hostname) + ':' + opts.port;
    location.origin = 'http://' + location.host;
  }
  if (opts.host) {
    location.hostname = opts.host;
    location.host = opts.host + ':' + location.port;
    location.origin = 'http://' + location.host;
  }
  if (opts.search !== undefined) location.search = opts.search;
  if (opts.base !== undefined) inst.window.__WB_BASE__ = opts.base;
  if (opts.viaGateway) inst.window.__WB_VIA_GATEWAY__ = true;

  const logs = [];
  const realLog = console.log;
  let api;
  console.log = (...args) => logs.push(args.join(' '));
  try {
    api = new Function(code + EXPORTS)();
  } finally {
    console.log = realLog;
  }
  // The page may kick off work from a load listener; settle it, then forget
  // those requests so a suite counts only what it asked for itself.
  await Promise.resolve();
  await Promise.resolve();
  calls.length = 0;
  return {
    api, calls, logs, inst,
    document: inst.document,
    window: inst.window,
    el: (id) => inst.document.getElementById(id),
  };
}

// Toast() logs through console.log before it renders, so this is how a suite
// reads what the user was told without modelling the toast DOM.
async function captureLogs(fn) {
  const seen = [];
  const realLog = console.log;
  console.log = (...args) => seen.push(args.join(' '));
  try { await fn(); } finally { console.log = realLog; }
  return seen;
}

(async function main() {
  console.log('dashboard: mount prefix, gateway gate and the number formatting');

  /* ---------------------------------------------------------------- static */
  await check('the page ships no prefix of its own - the server injects it', () => {
    eq(/<base[\s>]/i.test(bareHtml), false, 'the page must not carry its own <base>');
    eq(/window\.__WB_[A-Z_]+__\s*=(?!=)/.test(bareHtml), false, 'the page must not write the injected globals');
    ok(/window\.__WB_BASE__/.test(code), 'the page reads the injected mount prefix');
    ok(/window\.__WB_VIA_GATEWAY__/.test(code), 'the page reads whether it is behind the gateway');
    eq(/\/app\/[a-z0-9_.-]+/.test(bareHtml), false, 'no mount path is hardcoded in the page');
  });

  await check('every fetch in the page goes through wbUrl()', () => {
    const sites = [...html.matchAll(/\bfetch\(([^)]*)/g)].map(m => m[1].trim());
    eq(sites.length, 5, 'fetch call sites');
    for (const arg of sites) {
      ok(arg.startsWith('wbUrl('), 'a fetch bypasses the mount prefix: fetch(' + arg);
    }
  });

  await check('the help block sits inside the gateway page and is not a nav section', () => {
    ok(html.includes('id="helpApiBase"'), '#helpApiBase exists');
    ok(html.includes('id="helpLocalBase"'), '#helpLocalBase exists');
    ok(html.includes('id="wbHelp"'), '#wbHelp exists');
    const help = html.indexOf('id="wbHelp"');
    const end = html.indexOf('<!-- /pageGateway -->');
    ok(end > 0, 'the gateway page has an end marker');
    ok(help < end, 'the help block belongs to #pageGateway');
    eq(/<section[^>]*id="wbHelp"/.test(html), false, 'a <section> would add a second nav entry');
  });

  /* ---------------------------------------------------------------- direct */
  const direct = await boot({
    href: 'http://nas.local:8788/x',
    host: 'nas.local',
    port: '8788',
    routes: {
      '/panel/status': {authenticated: false, panel_password_is_default: false},
      // A wrong password is a 401 with the message the page shows, not a 200.
      '/panel/login': {status: 401, body: {error: {message: 'invalid panel password', type: 'invalid_request_error'}}},
    },
  });

  await check('direct: wbUrl leaves site-relative paths alone', () => {
    eq(direct.api.wbUrl('/tasks'), '/tasks');
    eq(direct.api.wbUrl('tasks'), '/tasks');
    eq(direct.api.wbUrl('/usage?realm=cn'), '/usage?realm=cn');
    eq(direct.api.wbUrl(null), '/');
  });

  await check('direct: wbUrl leaves another host alone', () => {
    eq(direct.api.wbUrl('https://openrouter.ai/api/v1/models'), 'https://openrouter.ai/api/v1/models');
    eq(direct.api.wbUrl('//cdn.example.com/app.js'), '//cdn.example.com/app.js');
  });

  await check('direct: getJSON and postJSON ask the bare path', async () => {
    await direct.api.getJSON('/tasks');
    await direct.api.postJSON('/settings/save', {a: 1});
    eq(direct.calls.map(c => c.url).join(' '), '/tasks /settings/save');
    eq(direct.calls[1].method, 'POST');
  });

  await check('direct: a password-protected panel still gets its password box', async () => {
    const gate = direct.el('panelGate');
    direct.document.body.appendChild(gate);
    direct.calls.length = 0;
    await captureLogs(() => direct.api.bootPanel());
    eq(direct.calls.map(c => c.url).join(' '), '/panel/status');
    eq(gate.style.display, 'flex', 'the gate is shown');
    ok(direct.document.body.childNodes.includes(gate), 'the gate stays in the page');
  });

  await check('direct: ?pwd= still logs in, and a rejected password is reported', async () => {
    direct.el('panelPwdInput').value = 'secret';
    direct.window.location.search = '?pwd=secret';
    direct.calls.length = 0;
    await captureLogs(() => direct.api.bootPanel());
    eq(direct.calls.map(c => c.url).join(' '), '/panel/status /panel/login');
    eq(direct.calls[1].method, 'POST');
    eq(direct.el('panelLoginMsg').textContent, 'invalid panel password');
  });

  await check('direct: the help addresses come from this origin', () => {
    direct.api.setPanelStatus({direct_port: 9999});
    const a = direct.api.helpAddresses();
    eq(a.api, 'http://nas.local:8788/v1');
    eq(a.local, 'http://nas.local:8788');
    direct.api.fillHelpAddresses();
    eq(direct.el('helpApiBase').textContent, 'http://nas.local:8788/v1');
    eq(direct.el('helpLocalBase').textContent, 'http://nas.local:8788');
  });

  /* --------------------------------------------------------------- gateway */
  const gateway = await boot({
    href: 'http://nas.local:8788/app/workbuddy2api/',
    host: 'nas.local',
    search: '?pwd=stale-password-from-an-old-tab',
    base: '/app/workbuddy2api',
    viaGateway: true,
    routes: {
      '/app/workbuddy2api/panel/status': {authenticated: false, via_gateway: true, direct_port: 9999},
      '/app/workbuddy2api/panel/login': {token: 'should-not-be-asked-for'},
    },
  });

  await check('gateway: wbUrl prefixes site-relative paths and nothing else', () => {
    eq(gateway.api.wbUrl('/tasks'), '/app/workbuddy2api/tasks');
    eq(gateway.api.wbUrl('accounts?realm=cn'), '/app/workbuddy2api/accounts?realm=cn');
    eq(gateway.api.wbUrl('/panel/status'), '/app/workbuddy2api/panel/status');
    eq(gateway.api.wbUrl('https://openrouter.ai/api/v1'), 'https://openrouter.ai/api/v1');
  });

  await check('gateway: requests carry the prefix and the password box is gone', async () => {
    const gate = gateway.el('panelGate');
    gateway.document.body.appendChild(gate);
    await gateway.api.getJSON('/models/locks');
    const logs = await captureLogs(() => gateway.api.bootPanel());
    eq(gateway.calls.map(c => c.url).join(' '), '/app/workbuddy2api/models/locks /app/workbuddy2api/panel/status');
    eq(gateway.document.body.childNodes.includes(gate), false, 'the gate is removed from the page');
    ok(logs.join('\n').includes('应用中心'), 'the user is told to reopen it from the App Center');
    eq(/panel\/login/.test(gateway.calls.map(c => c.url).join(' ')), false, 'no password is ever asked for behind the gateway');
    eq(gate.style.display, '', 'the gate is not merely hidden - it is out of the page');
  });

  await check('gateway: the emergency address is this host on the port /panel/status reported', () => {
    const a = gateway.api.helpAddresses();
    eq(a.api, 'http://nas.local:9999/v1', 'the configurable port comes from the server, not from 8788');
    eq(a.local, 'http://nas.local:9999');
    gateway.api.fillHelpAddresses();
    eq(gateway.el('helpLocalBase').textContent, 'http://nas.local:9999');
  });

  await check('gateway: a lost session does not resurrect the password box', async () => {
    const gate = gateway.el('panelGate');
    gateway.document.body.appendChild(gate);
    const logs = await captureLogs(() => gateway.api.panelNeedsLogin());
    eq(gateway.document.body.childNodes.includes(gate), false, 'still removed');
    ok(logs.join('\n').includes('应用中心'), 'the toast offers the App Center way back');
  });

  /* --------------------------------------------------------- the numbers */
  const last = gateway.api;

  await check('fmtTok: exact below 100k, switching units above, never 1000K', () => {
    eq(last.fmtTok(0), '0');
    eq(last.fmtTok(8300), '8,300');
    eq(last.fmtTok(99999), '99,999');
    eq(last.fmtTok(100000), '100K');
    eq(last.fmtTok(150000), '150K');
    eq(last.fmtTok(999999), '1M', '999,999 rounds into the next unit');
    eq(last.fmtTok(2500000), '2.5M');
    eq(last.fmtTok(12500000), '12.5M');
    eq(last.fmtTok(125000000), '125M');
    eq(last.fmtTok(1500000000), '1.5B');
    eq(last.fmtTok(undefined), '0', 'a missing figure reads as zero, not NaN');
  });

  await check('creditPerM: no tokens is unknown, no credit is a real zero', () => {
    eq(last.creditPerM(5, 2000000), 2.5);
    eq(last.creditPerM(0, 2000000), 0, 'ran but spent nothing');
    eq(last.creditPerM(5, 0), null, 'no tokens, no ratio');
    eq(last.creditPerM(5, undefined), null);
    eq(last.creditPerM(null, 1000), 0);
    eq(last.fmtPerM(5, 2000000), '<b style="color:var(--accent2)">2.50</b>');
    eq(last.fmtPerM(0, 2000000), '<span style="color:var(--dim)">0</span>');
    ok(last.fmtPerM(5, 0).includes('—'), 'unknown renders as a dash, not 0');
  });

  await check('the matrix carries a per-million-token credit column', () => {
    eq([...html.matchAll(/data-label="每 M tokens 积分"/g)].length, 2, 'summary row and data rows');
    eq([...html.matchAll(/每 M tokens 积分/g)].length, 3, 'plus the header cell');
    const dsRow = (req, tok, credit) => ({
      requests: req, total_tokens: tok, prompt_tokens: tok - 1000, completion_tokens: 1000,
      reasoning_tokens: 0, cached_tokens: 0, credit,
    });
    const usage = {
      requests: 3, total_tokens: 3000000, prompt_tokens: 2998000, completion_tokens: 2000,
      reasoning_tokens: 0, credit: 6.25,
      by_model: {
        'glm-5.3': dsRow(2, 2000000, 5),
        'deepseek-v4.1-flash': dsRow(1, 1000000, 1.25),
      },
      by_model_realm: {
        'glm-5.3': {intl: dsRow(2, 2000000, 5)},
        'deepseek-v4.1-flash': {intl: dsRow(1, 1000000, 1.25)},
      },
      by_model_acct: {
        'glm-5.3': {intl: {'acct-A': dsRow(2, 2000000, 5)}},
        'deepseek-v4.1-flash': {intl: {'acct-B': dsRow(1, 1000000, 1.25)}},
      },
      accounts_map: {'acct-A': {nickname: 'Hades', realm: 'intl'}, 'acct-B': {nickname: 'lenguedogahz', realm: 'intl'}},
    };
    const stat = (n) => ({avg: n, p50: n, samples: 1});
    const perf = {
      errors: 0, ttft_ms: stat(400), tokens_per_sec: stat(100), wall_ms: stat(1200),
      cache_hit_pct: {avg: 0, samples: 0},
      by_model: {
        'glm-5.3': {errors: 0, ttft_ms: stat(900), tokens_per_sec: stat(50), wall_ms: stat(3000), cache_hit_pct: {avg: 0, samples: 0}},
        'deepseek-v4.1-flash': {errors: 0, ttft_ms: stat(400), tokens_per_sec: stat(100), wall_ms: stat(1200), cache_hit_pct: {avg: 0, samples: 0}},
      },
      by_model_realm: {
        'glm-5.3': {intl: {errors: 0, ttft_ms: stat(900), tokens_per_sec: stat(50), wall_ms: stat(3000), cache_hit_pct: {avg: 0, samples: 0}}},
        'deepseek-v4.1-flash': {intl: {errors: 0, ttft_ms: stat(400), tokens_per_sec: stat(100), wall_ms: stat(1200), cache_hit_pct: {avg: 0, samples: 0}}},
      },
    };
    last.renderPerfMatrix(usage, perf);
    const matrix = last.__matrixHtml || (gateway.el('perfMatrix').innerHTML || '');
    ok(matrix.includes('每 M tokens 积分'), 'the header names the column');
    ok(matrix.includes('>2.50</b>'), 'glm-5.3: 5 credit over 2M tokens');
    ok(matrix.includes('>1.25</b>'), 'deepseek-v4.1-flash: 1.25 credit over 1M tokens');
    ok(matrix.includes('>2.08</b>'), 'the summary row divides the totals');
  });

  // 两个上游套件（tests/_test_matrix_filters.js 与 tests/_test_usage_share.js）把 token 那格钉成
  // 裸形态：`<td data-label="总 Token">` 后面必须紧跟 `>`，内层还是 `<b style="color:var(--accent)">`。
  // 所以精确 token 数只能挂在整行上——这条断言把该约束钉死，防止以后又把 title 加回 <td>。
  await check('the token column keeps the bare tag the upstream suites pin', () => {
    const html = gateway.el('perfMatrix').innerHTML || '';
    ok(html.includes('<td data-label="总 Token"><b style="color:var(--accent)">'),
       'the summary token cell is the upstream literal shape');
    ok(html.includes('<td data-label="总 Token"><b>'), 'the data row token cell is bare too');
    ok(!/data-label="总 Token"[^>]*title=/.test(html), 'no title attribute on that <td>');
    ok(/<tr[^>]*title="[^"]*token（输入 /.test(html), 'the exact figures ride on the row instead');
  });

  await check('fmtK (model capabilities) gained a billion step', () => {
    // The page reads MODELS_DATA as a bare global, and in a browser `window` IS
    // the global - the stub keeps the two apart, so seed both.
    const models = [{
      id: 'step-3.5-flash', name: 'Step 3.5 Flash', vendor: 'StepFun',
      context_length: 1500000000, max_output_tokens: 64000, credits: 0,
    }];
    gateway.window.MODELS_DATA = models;
    global.MODELS_DATA = models;
    last.renderAvailableModels();
    const rendered = gateway.document.querySelector('#modelsTable tbody').innerHTML || '';
    ok(/1\.5B/.test(rendered), 'a 1.5e9 context window reads as 1.5B, not 1500M: ' + rendered.slice(0, 200));
    eq(/NaN|undefined/.test(rendered), false, 'no NaN leaks into the table');
  });

  /* ------------------------------------------------------------- fallbacks */
  await check('the page is readable on a phone', () => {
    ok(/-webkit-text-size-adjust:\s*100%/.test(style), 'text size is not re-scaled on rotation');
    ok(/safe-area-inset-(top|bottom|left|right)/.test(style), 'the notch and home bar are respected');
    ok(/font-size:\s*16px/.test(style), 'inputs stay at 16px so iOS does not zoom the viewport');
    ok(!/\.wb-help[^{]*\{[^}]*position:\s*absolute/.test(style), 'the help block is laid out in flow, not stacked over the page');
  });

  console.log((failures ? '  ' : '  ') + checks + ' checks passed' + (failures ? ', ' + failures + ' failed' : ''));
  if (failures) process.exit(1);
})().catch((err) => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
