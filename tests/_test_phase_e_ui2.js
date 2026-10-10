/* WP-E6: the cockpit-compatible account export, page half.
 *
 * The gateway can write two export formats:
 *   native  - what `POST /accounts/export` with no format, or the plain GET,
 *             returns today: the document this panel re-imports itself.
 *   cockpit - a bare array, snake_case, credentials included, handed to another
 *             panel (fnOS App Center style). Cockpit rows carry no realm field
 *             at all - the receiving panel derives cn/intl from `domain` - so the
 *             server demands an explicit realm, and one file is one realm.
 *
 * The server half is pinned in tests/_test_cockpit_export.py. This suite boots
 * the shipped page against a fake DOM and holds the page to the same contract
 * (wb_proxy.py:7950 `_route_accounts_export`, reached from wb_proxy.py:8748):
 *
 *   POST /accounts/export  {"format":"cockpit","realm":"cn"}
 *     -> 200 {"ok":true,"format":..,"filename":"..cockpit.json","count":N,"data":[...]}
 *     -> 400 {"error":{"message":"realm must be cn or intl"}}   (and friends)
 *     -> 404 {"error":{"message":"no such account: .."}}
 *     -> 401 when the panel session is gone
 *
 * Two things a reader meets are pinned statically: the toolbar entry (a realm
 * picker beside the upstream 导出账号 button, which must not break the narrow
 * layout) and the help line that says which file travels in which direction.
 *
 *   node _test_phase_e_ui2.js
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
// The accounts toolbar, as markup: from the first toolbar button through the
// cockpit group that closes it. The upstream v1.6.19 toolbar is
// 扫描桌面客户端 / 导入 / 导出 / <span class="toolbar-sep"> / 一键刷新积分,
// and the cockpit pair sits right after 导出, so the slice runs from the scan
// button to the separator that follows the cockpit button.
const toolbar = (() => {
  const from = bareHtml.indexOf('id="btnScanDesktop"');
  const to = bareHtml.indexOf('toolbar-sep', from);
  // Up to and including the separator's opening tag, so the group boundary is
  // part of what is checked.
  return from >= 0 && to > from ? bareHtml.slice(from, to + 20) : '';
})();
const cssRule = (sel) => {
  const i = style.indexOf(sel);
  return i < 0 ? '' : style.slice(i, style.indexOf('}', i) + 1);
};
// The page styles selects at 16px on phones unless something overrides it.
const selectRule = (style.match(/input:not\(\[type=checkbox\]\):not\(\[type=radio\]\),\s*select,\s*textarea\{[^}]*\}/) || [''])[0];

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
const includes = (haystack, needle, what) =>
  assert.ok(String(haystack).indexOf(needle) >= 0, (what || '') + ': expected to find ' + JSON.stringify(needle));

/* What the page script keeps in its own scope. Everything below is reached
 * through here rather than through globals, because the script is one function
 * body and only what it returns is addressable. */
const EXPORTS = `
    return {
      wbUrl, authHeaders,
      downloadExport, exportAccounts, exportAccountsCockpit,
      helpAddresses, fillHelpAddresses,
    };`;

/* Boot the real page against a fake DOM. `routes` is keyed by
 * `'<METHOD> <url>'` first and by bare url second; a value may be a body, a
 * `{status, body, raw}` envelope, a function, or null for a bare 404. */
async function boot(opts) {
  opts = opts || {};
  const calls = [];
  const routes = opts.routes || {};
  const reply = (status, body, raw) => ({
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(raw === undefined ? JSON.stringify(body) : raw),
  });
  const inst = dom.installDom({
    querySelector: {'#modelsTable tbody': dom.makeElement('tbody', {permissive: true})},
    fetch: (url, options) => {
      const u = String(url);
      const method = (options && options.method) || 'GET';
      const record = {
        url: u,
        method,
        headers: (options && options.headers) || {},
        body: options ? options.body : undefined,
      };
      calls.push(record);
      let route = routes[method + ' ' + u];
      if (route === undefined) route = routes[u];
      if (typeof route === 'function') route = route(record);
      if (route === null) return Promise.resolve(reply(404, {}));
      if (route && typeof route === 'object' && typeof route.status === 'number') {
        return Promise.resolve(reply(route.status, route.body === undefined ? {} : route.body, route.raw));
      }
      return Promise.resolve(reply(200, route === undefined ? {} : route));
    },
  });

  // The blob and the <a download> are the file the user gets; keep them.
  const anchors = [];
  const realCreate = inst.document.createElement;
  inst.document.createElement = (tag) => {
    const el = realCreate(tag);
    if (String(tag).toLowerCase() === 'a') anchors.push(el);
    return el;
  };
  const api = new Function(code + EXPORTS)();
  await Promise.resolve();
  await Promise.resolve();
  calls.length = 0;

  return {
    api, calls, inst, anchors,
    document: inst.document,
    window: inst.window,
    el: (id) => inst.document.getElementById(id),
    // The page saves the file through a blob URL plus a synthetic <a download>.
    // Capture both for the duration of one call, and collect what the user was
    // told (toast() logs through console.log before it renders).
    async run(fn) {
      const realObjectURL = URL.createObjectURL;
      const realRevoke = URL.revokeObjectURL;
      const realLog = console.log;
      let blob = null;
      const seen = [];
      URL.createObjectURL = (b) => { blob = b; return 'blob:phase-e'; };
      URL.revokeObjectURL = () => {};
      console.log = (...args) => seen.push(args.join(' '));
      anchors.length = 0;
      try {
        await fn();
      } finally {
        console.log = realLog;
        URL.createObjectURL = realObjectURL;
        URL.revokeObjectURL = realRevoke;
      }
      const text = blob ? await blob.text() : null;
      return {text, name: anchors.length ? anchors[anchors.length - 1].download : null, logs: seen};
    },
  };
}

const COCKPIT_OK = {
  ok: true,
  format: 'cockpit',
  filename: 'workbuddy-cockpit-cn-20260101.cockpit.json',
  count: 2,
  data: [
    {domain: 'workbuddy.cn', access_token: 'at-cn', refresh_token: 'rt-cn', enabled: true, remark: 'a'},
    {domain: 'workbuddy.cn', access_token: 'at-cn-2', refresh_token: 'rt-cn-2', enabled: false, remark: 'b'},
  ],
};
const post = (r) => r.calls.filter(c => c.method === 'POST');
const reqOf = (r) => { const p = post(r); eq(p.length, 1, 'exactly one POST'); return p[0]; };

(async function main() {
  console.log('dashboard: cockpit-compatible account export');

  /* ---------------------------------------------------------------- static */
  await check('the toolbar offers a cockpit export beside the upstream button', () => {
    ok(toolbar, 'the accounts toolbar was located');
    includes(toolbar, 'id="cockpitRealm"', 'a realm picker in the toolbar');
    includes(toolbar, 'onclick="exportAccountsCockpit(this)"', 'the cockpit button');
    eq(/<option value="cn">/.test(toolbar), true, 'the cn option');
    eq(/<option value="intl">/.test(toolbar), true, 'the intl option');
    // The native button and the import button must keep their own handlers.
    includes(toolbar, 'onclick="exportAccounts(this)"', 'the upstream export button');
    includes(toolbar, 'onclick="openImport()"', 'the import button');
  });

  await check('the realm picker cannot blow the toolbar apart on a narrow screen', () => {
    const rule = cssRule('#cockpitRealm{');
    ok(rule, 'the picker has its own rule (button.sec does not match a <select>)');
    includes(rule, 'max-width:100%', 'a long option label may not push the toolbar wide');
    includes(rule, 'min-width:0', 'flex children need min-width:0 to be allowed to shrink');
    eq(/[^-]width:\s*[0-9]/.test(rule), false, 'no fixed width');
    eq(/white-space:\s*nowrap/.test(rule), false, 'no nowrap');
    // The toolbar itself must still wrap, in the base rule and on phones.
    eq(/\.toolbar\{[^}]*flex-wrap:wrap/.test(style), true, 'the toolbar wraps');
    includes(style, '.toolbar{gap:6px}', 'the phone toolbar still tightens its gap');
  });

  await check('the phone rules still keep selects at 16px and thumb-sized', () => {
    ok(selectRule, 'the 16px select rule survived');
    includes(selectRule, 'font-size:16px!important', 'iOS must not zoom on focus');
    const phone = style.slice(style.indexOf(selectRule));
    includes(phone, '#cockpitRealm{min-height:40px}', 'the picker is a real touch target on phones');
  });

  await check('the help section says which export goes which way', () => {
    const i = html.indexOf('id="helpExportNote"');
    ok(i > 0, 'the help line exists');
    const line = html.slice(i, html.indexOf('</div>', i));
    includes(line, 'cockpit', 'it names the cockpit format');
    includes(line, 'native', 'it names the native format');
    includes(line, '回灌本网关', 'it says the native file comes back here');
    ok(html.indexOf('id="helpExportNote"') > html.indexOf('id="wbHelp"'), 'the line lives inside the help section');
  });

  await check('the English dictionary covers the new controls', () => {
    includes(code, "'导出 (cockpit 兼容)': 'Export (cockpit-compatible)'", 'the button label');
    includes(code, "'cockpit 导出：国内版': 'cockpit export: China'", 'the cn option');
    includes(code, "'cockpit 导出：国际版': 'cockpit export: Global'", 'the intl option');
  });

  /* --------------------------------------------------------------- runtime */
  const r = await boot({routes: {'POST /accounts/export': COCKPIT_OK}});
  await check('the dictionary really resolves the new labels at runtime', () => {
    const t = r.window.WB_I18N && r.window.WB_I18N.translate;
    ok(typeof t === 'function', 'WB_I18N.translate is exposed');
    eq(t('导出 (cockpit 兼容)'), 'Export (cockpit-compatible)');
    eq(t('cockpit 导出：国内版'), 'cockpit export: China');
  });

  await check('cockpit export posts format+realm and saves the bare array', async () => {
    const btn = {disabled: false, textContent: '导出 (cockpit 兼容)'};
    const out = await r.run(() => r.api.exportAccountsCockpit(btn));
    const req = reqOf(r);
    eq(req.url, '/accounts/export', 'the export endpoint');
    eq(req.method, 'POST', 'the format is stated in the body');
    includes(String(req.headers['Content-Type']), 'application/json', 'a JSON body needs the header');
    const sent = JSON.parse(req.body);
    eq(sent.format, 'cockpit', 'the format');
    eq(sent.realm, 'cn', 'the default realm is cn');
    eq(Object.keys(sent).sort().join(','), 'format,realm', 'nothing else is sent (secrets:false would be a 400)');
    // The file is the cockpit document itself, not the HTTP envelope.
    const file = JSON.parse(out.text);
    eq(Array.isArray(file), true, 'the file is a bare array');
    eq(file.length, 2, 'both rows are in the file');
    eq(file[0].access_token, 'at-cn', 'credentials travel with it, as the format promises');
    eq(out.text, JSON.stringify(COCKPIT_OK.data, null, 2), 'written pretty-printed');
    eq(out.name, COCKPIT_OK.filename, 'the server names the file, so it matches its own logging');
    includes(out.logs.join('\n'), '已导出 2 个国内版账号（cockpit 兼容）', 'the count and realm are reported');
    includes(out.logs.join('\n'), COCKPIT_OK.filename, 'the file name is reported');
    eq(btn.disabled, false, 'the button is usable again');
    eq(btn.textContent, '导出 (cockpit 兼容)', 'and labelled as before');
  });

  await check('the intl choice is what gets posted', async () => {
    const r2 = await boot({routes: {'POST /accounts/export': {ok: true, format: 'cockpit', filename: 'intl.cockpit.json', count: 1, data: [{domain: 'workbuddy.ai'}]}}});
    r2.el('cockpitRealm').value = 'intl';
    const res = await r2.run(() => r2.api.exportAccountsCockpit({disabled: false, textContent: 'x'}));
    const sent = JSON.parse(reqOf(r2).body);
    eq(sent.realm, 'intl', 'the selected realm is posted');
    eq(sent.format, 'cockpit', 'the format stays cockpit');
    includes(res.logs.join('\n'), '已导出 1 个国际版账号（cockpit 兼容）', 'the report names the realm that was exported');
  });

  await check('a server filename is used, but never a hostile one', async () => {
    const good = await boot({routes: {'POST /accounts/export': {ok: true, filename: 'my-export.cockpit.json', count: 1, data: [{}]}}});
    const a = await good.run(() => good.api.exportAccountsCockpit({}));
    eq(a.name, 'my-export.cockpit.json', 'a plain server name is honoured');

    const bad = await boot({routes: {'POST /accounts/export': {ok: true, filename: '../evil.json', count: 1, data: [{}]}}});
    const b = await bad.run(() => bad.api.exportAccountsCockpit({}));
    eq(b.name.indexOf('evil') >= 0, false, 'a name with a path in it is refused');
    eq(/^workbuddy-accounts-\d{14}\.json$/.test(String(b.name)), true, 'and the local fallback name is used: ' + b.name);
  });

  await check('the reported count comes from the envelope, not from the file', async () => {
    const r3 = await boot({routes: {'POST /accounts/export': {ok: true, filename: 'x.cockpit.json', count: 7, data: [{}]}}});
    const out = await r3.run(() => r3.api.exportAccountsCockpit({}));
    includes(out.logs.join('\n'), '已导出 7 个', 'the server count wins (rows can be rewritten server-side)');
  });

  await check('a 400 is shown as the server worded it', async () => {
    const r4 = await boot({routes: {'POST /accounts/export': {status: 400, body: {error: {message: 'realm must be cn or intl'}}}}});
    const btn = {disabled: false, textContent: '导出 (cockpit 兼容)'};
    const out = await r4.run(() => r4.api.exportAccountsCockpit(btn));
    eq(out.text, null, 'nothing was downloaded');
    includes(out.logs.join('\n'), 'cockpit 导出失败: realm must be cn or intl', 'the server sentence reaches the user');
    eq(btn.disabled, false, 'the button is usable again after a failure');
    eq(btn.textContent, '导出 (cockpit 兼容)', 'with its own label');
  });

  await check('a 404 without a JSON body still says something actionable', async () => {
    const r5 = await boot({routes: {'POST /accounts/export': null}});
    const out = await r5.run(() => r5.api.exportAccountsCockpit({}));
    eq(out.text, null, 'nothing was downloaded');
    includes(out.logs.join('\n'), '网关不认识这个导出请求', 'the page explains it rather than printing HTTP 404 alone');
  });

  await check('a lost panel session is reported, and downloads nothing', async () => {
    const r6 = await boot({routes: {'POST /accounts/export': {status: 401, body: {error: {message: 'unauthorized'}}}}});
    const out = await r6.run(() => r6.api.exportAccountsCockpit({}));
    eq(out.text, null, 'nothing was downloaded');
    ok(out.logs.some(l => l.indexOf('cockpit 导出失败') >= 0), 'the failure is reported: ' + out.logs.join(' | '));
  });

  await check('the native export path is unchanged', async () => {
    const doc = {count: 1, accounts: [{uid: 'a', access_token: 'tok'}]};
    // A double space survives JSON.stringify -> the GET path must write the
    // bytes it was handed, not a re-serialisation of them.
    const raw = '{"count":1,  "accounts":[{"uid":"a","access_token":"tok"}]}';
    const r7 = await boot({routes: {'GET /accounts/export': {status: 200, body: doc, raw: raw}}});
    const out = await r7.run(() => r7.api.exportAccounts({}));
    const req = r7.calls[0];
    eq(req.url, '/accounts/export', 'the same endpoint');
    eq(req.method, 'GET', 'no method override');
    eq(req.body, undefined, 'and no body');
    eq(out.text, raw, 'the server bytes are written as-is');
    eq(/^workbuddy-accounts-\d{14}\.json$/.test(String(out.name)), true, 'the local name: ' + out.name);
    includes(out.logs.join('\n'), '已导出 1 个账号', 'the upstream report');
  });

  await check('a GET failure is still reported the upstream way', async () => {
    const r8 = await boot({routes: {'GET /accounts/export': {status: 400, body: {error: {message: 'nope'}}}}});
    const out = await r8.run(() => r8.api.exportAccounts({}));
    includes(out.logs.join('\n'), '导出失败: HTTP 400', 'the GET path keeps its terse wording');
  });

  console.log((failures ? '  ' : '') + checks + ' checks passed' + (failures ? ', ' + failures + ' failed' : ''));
  if (failures) process.exit(1);
})();
