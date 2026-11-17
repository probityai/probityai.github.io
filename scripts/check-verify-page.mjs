// Check the in-browser record checker at verify/ in a real headless Chrome, without a browser framework:
// a page whose Pyodide lock file was altered in transit never loads the reader, the pinned reader loads with all
// three runtime files checked, the example record is ADMITTED with verdict pass, two edits are REFUSED, and a
// record with a duplicate member is refused as the command line refuses it.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { extname, join, normalize, resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(process.argv[2] ?? '.');
const types = { '.html': 'text/html; charset=utf-8', '.json': 'application/json' };
const server = createServer(async (request, response) => {
  const path = new URL(request.url, 'http://x').pathname;
  const file = normalize(join(root, path.endsWith('/') ? `${path}index.html` : path));
  if (!file.startsWith(join(root, 'verify'))) { response.writeHead(404); response.end(); return; }
  try {
    const body = await readFile(file);
    response.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream' });
    response.end(body);
  } catch { response.writeHead(404); response.end(); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const page = `http://127.0.0.1:${server.address().port}/verify/`;
const profile = await mkdtemp(join(tmpdir(), 'verify-page-'));
const browser = spawn(process.env.CHROME_BIN ?? 'google-chrome', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
], { stdio: 'ignore' });

async function until(check, label, milliseconds = 30_000) {
  const end = Date.now() + milliseconds;
  while (Date.now() < end) {
    const value = await check();
    if (value) return value;
    await delay(250);
  }
  throw new Error(`Timed out: ${label}`);
}

let socket, sequence = 0;
const pending = new Map();
const listeners = new Map();
function cdp(method, params = {}) {
  const id = ++sequence;
  return new Promise((done, fail) => {
    const timer = setTimeout(() => { pending.delete(id); fail(new Error(`CDP timeout: ${method}`)); }, 60_000);
    pending.set(id, { done, fail, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert(!result.exceptionDetails, JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
const status = () => evaluate('document.getElementById("status").textContent');

// Click "Load the example" and wait for THIS click's load to finish. Waiting on the record's length instead
// passed at once on every reload after the first (the old example was still in the box), so the edit that
// followed was overwritten when the fetch completed and the check ran on the unedited example.
async function loadExample(label) {
  const before = await evaluate('Number(document.body.dataset.exampleLoads ?? 0)');
  await evaluate('document.getElementById("example").click()');
  await until(() => evaluate(`Number(document.body.dataset.exampleLoads ?? 0) > ${before}`), label);
}

async function run(label) {
  await evaluate('document.getElementById("status").textContent = ""; document.getElementById("run").click()');
  const text = await until(status, `verdict for ${label}`);
  console.log(`${label}: ${text}`);
  return text;
}

try {
  const port = await until(async () => {
    try { return (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; }
    catch { return null; }
  }, 'Chrome debug port');
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  socket = new WebSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  await new Promise((done, fail) => { socket.onopen = done; socket.onerror = fail; });
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method) { listeners.get(message.method)?.(message.params); return; }
    const item = message.id && pending.get(message.id);
    if (!item) return;
    pending.delete(message.id); clearTimeout(item.timer);
    message.error ? item.fail(new Error(JSON.stringify(message.error))) : item.done(message.result);
  };
  await cdp('Page.enable');
  // No cached runtime file may stand in for a network read, and the altered lock file must not be reused.
  await cdp('Network.enable');
  await cdp('Network.setCacheDisabled', { cacheDisabled: true });
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 900, deviceScaleFactor: 1, mobile: true });
  const loaded = () => evaluate('document.body?.dataset.ready === "true" || document.getElementById("status")?.dataset.result === "ERROR"');

  // Counter-example: one byte added to each pinned runtime file on its way from the CDN, one file per load. The
  // page must refuse to load the reader rather than run a runtime its pins do not describe. A byte appended to the
  // standard library zip still opens as a zip, so only the page's own pin can refuse that one.
  for (const name of ['pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
    let tampered = 0;
    listeners.set('Fetch.requestPaused', async ({ requestId, responseStatusCode, responseHeaders }) => {
      const { body, base64Encoded } = await cdp('Fetch.getResponseBody', { requestId });
      const bytes = Buffer.concat([Buffer.from(body, base64Encoded ? 'base64' : 'utf8'), Buffer.from(' ')]);
      tampered += 1;
      await cdp('Fetch.fulfillRequest', { requestId, responseCode: responseStatusCode, responseHeaders, body: bytes.toString('base64') });
    });
    await cdp('Fetch.enable', { patterns: [{ urlPattern: `*/${name}`, requestStage: 'Response' }] });
    // Mark the current document, so the wait below cannot read the previous load's refusal as this one's.
    await evaluate('document.body && (document.body.dataset.stale = "true")');
    await cdp('Page.navigate', { url: page });
    await until(() => evaluate('document.body?.dataset.stale !== "true" && document.getElementById("status")?.dataset.result === "ERROR" || document.body?.dataset.ready === "true"'), `tampered ${name} refused`, 180_000);
    const refusal = await status();
    console.log(`tampered ${name}: ${refusal}`);
    assert.equal(tampered, 1, `the ${name} request was not intercepted, so the counter-example tested nothing`);
    const quoted = name.replace(/\./g, '\\.');
    assert.match(refusal, new RegExp(`^The reader did not load: runtime file ${quoted} digest [0-9a-f]{64} differs`));
    assert.equal(await evaluate('document.getElementById("run").disabled'), true);
    await cdp('Fetch.disable');
    listeners.delete('Fetch.requestPaused');
  }

  await cdp('Page.navigate', { url: page });
  // Pyodide, its standard library and the 12 MB wheel come over the network: allow three minutes.
  await until(() => evaluate(`location.href === ${JSON.stringify(page)} && document.readyState === "complete" && !document.getElementById("status").dataset.result`), 'page loaded');
  await until(loaded, 'reader loaded', 180_000);
  assert.equal(await evaluate('document.body.dataset.ready'), 'true', `reader failed: ${await status()}`);
  assert.equal(await evaluate('document.body.dataset.runtime'), '3 of 3 runtime files checked');
  const layout = await evaluate('({width: innerWidth, content: document.documentElement.scrollWidth})');
  assert(layout.content <= layout.width, `horizontal overflow at 390 px: ${JSON.stringify(layout)}`);

  await loadExample('example loaded');
  assert.equal(await run('example'), 'ADMITTED, verdict pass');

  await evaluate(`(() => { const r = JSON.parse(document.getElementById("record").value);
    r.verdict = "fail"; document.getElementById("record").value = JSON.stringify(r); })()`);
  assert.match(await run('verdict rewritten'), /^REFUSED: .*VERDICT_CONTRADICTED/);

  await loadExample('example reloaded for the case-set edit');
  await evaluate(`(() => { const c = JSON.parse(document.getElementById("case-sets").value);
    c[0].cases[2].expect = "verified"; document.getElementById("case-sets").value = JSON.stringify(c); })()`);
  assert.match(await run('expectation flipped in the held case set'), /^REFUSED: .*CASE_SET_UNRESOLVED/);

  // Counter-example: a record whose first "verdict" says fail and whose last says pass. A last-wins parser
  // admitted it with verdict pass while "agent-evidence-vectors claim verify" refuses the same bytes.
  await loadExample('example reloaded for the duplicate member');
  const edited = await evaluate(`(() => { const box = document.getElementById("record");
    box.value = box.value.replace('"verdict": "pass"', '"verdict": "fail", "verdict": "pass"');
    return box.value.includes('"verdict": "fail", "verdict": "pass"'); })()`);
  assert.equal(edited, true, 'the duplicate member was not written into the record, so the counter-example tested nothing');
  assert.match(await run('duplicate verdict member'), /^Could not read the input: .*duplicate member/);

  await evaluate('document.getElementById("record").value = "{not json"');
  assert.match(await run('malformed input'), /^Could not read the input/);

  // A failed example load must say so and must not leave a waiter hanging: before this the page threw an
  // unhandled rejection on a dropped connection or a body that was not JSON, and the status stayed empty.
  for (const [label, body, expected] of [
    ['no network', 'Promise.reject(new TypeError("Failed to fetch"))', /^The example did not load: Failed to fetch/],
    ['body not JSON', 'Promise.resolve(new Response("<html>"))', /^The example did not load: /],
    ['wrong shape', 'Promise.resolve(new Response("{}"))', /^The example did not load: example.json has no record/],
  ]) {
    const failures = await evaluate('Number(document.body.dataset.exampleFailures ?? 0)');
    await evaluate(`(() => { const real = window.fetch; window.__realFetch = real;
      window.fetch = url => String(url).endsWith("example.json") ? ${body} : real(url);
      document.getElementById("status").textContent = ""; document.getElementById("example").click(); })()`);
    await until(() => evaluate(`Number(document.body.dataset.exampleFailures ?? 0) > ${failures}`), `example failure: ${label}`);
    await evaluate('window.fetch = window.__realFetch');
    assert.match(await status(), expected, `example failure: ${label}`);
  }
  console.log('verify page: 7 of 7 checks passed');
} catch (error) {
  console.error(error.stack ?? error);
  process.exitCode = 1;
} finally {
  socket?.close();
  browser.kill('SIGTERM');
  server.close();
  await delay(500);
  await rm(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
}
