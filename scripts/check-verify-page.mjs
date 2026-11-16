// Check the in-browser record checker at verify/ in a real headless Chrome, without a browser framework:
// the pinned reader loads, the example record is ADMITTED with verdict pass, two edits are REFUSED, and a record
// with a duplicate member is refused as the command line refuses it.
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
    const item = message.id && pending.get(message.id);
    if (!item) return;
    pending.delete(message.id); clearTimeout(item.timer);
    message.error ? item.fail(new Error(JSON.stringify(message.error))) : item.done(message.result);
  };
  await cdp('Page.enable');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 900, deviceScaleFactor: 1, mobile: true });
  await cdp('Page.navigate', { url: page });
  // Pyodide, its standard library and the 12 MB wheel come over the network: allow three minutes.
  await until(() => evaluate(`location.href === ${JSON.stringify(page)} && document.readyState === "complete"`), 'page loaded');
  await until(() => evaluate('document.body?.dataset.ready === "true" || document.getElementById("status")?.dataset.result === "ERROR"'),
    'reader loaded', 180_000);
  assert.equal(await evaluate('document.body.dataset.ready'), 'true', `reader failed: ${await status()}`);
  const layout = await evaluate('({width: innerWidth, content: document.documentElement.scrollWidth})');
  assert(layout.content <= layout.width, `horizontal overflow at 390 px: ${JSON.stringify(layout)}`);

  await evaluate('document.getElementById("example").click()');
  await until(() => evaluate('document.getElementById("record").value.length > 100'), 'example loaded');
  assert.equal(await run('example'), 'ADMITTED, verdict pass');

  await evaluate(`(() => { const r = JSON.parse(document.getElementById("record").value);
    r.verdict = "fail"; document.getElementById("record").value = JSON.stringify(r); })()`);
  assert.match(await run('verdict rewritten'), /^REFUSED: .*VERDICT_CONTRADICTED/);

  await evaluate('document.getElementById("example").click()');
  await delay(500);
  await evaluate(`(() => { const c = JSON.parse(document.getElementById("case-sets").value);
    c[0].cases[2].expect = "verified"; document.getElementById("case-sets").value = JSON.stringify(c); })()`);
  assert.match(await run('expectation flipped in the held case set'), /^REFUSED: .*CASE_SET_UNRESOLVED/);

  // Counter-example: a record whose first "verdict" says fail and whose last says pass. A last-wins parser
  // admitted it with verdict pass while "agent-evidence-vectors claim verify" refuses the same bytes.
  await evaluate('document.getElementById("example").click()');
  await until(() => evaluate('document.getElementById("record").value.length > 100'), 'example reloaded');
  await evaluate(`(() => { const box = document.getElementById("record");
    box.value = box.value.replace('"verdict": "pass"', '"verdict": "fail", "verdict": "pass"'); })()`);
  assert.match(await run('duplicate verdict member'), /^Could not read the input: .*duplicate member/);

  await evaluate('document.getElementById("record").value = "{not json"');
  assert.match(await run('malformed input'), /^Could not read the input/);
  console.log('verify page: 5 of 5 checks passed');
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
