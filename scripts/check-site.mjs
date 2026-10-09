// Check the published task contract in a real browser, without a browser framework.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { createServer } from 'node:http';
import { mkdtemp, mkdir, readFile, writeFile, rm } from 'node:fs/promises';
import { createWriteStream } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(process.argv[2] ?? '.');
const out = resolve(process.env.SITE_CHECK_OUTPUT ?? 'site-check-artifacts');
await mkdir(out, { recursive: true });
const profile = await mkdtemp(join(tmpdir(), 'probity-site-'));
const html = await readFile(join(root, 'index.html'));
const tasks = [
  ['Test a verifier', 'https://probityai.github.io/agent-evidence-vectors/start.html'],
  ['Replay an evidence decision', 'https://probityai.github.io/agent-evidence-atlas/replay-an-evidence-decision.html'],
  ['Choose a component', 'https://probityai.github.io/agent-evidence-atlas/start.html'],
  ['Inspect or contribute a run', 'https://probityai.github.io/agent-evidence-atlas/lab.html'],
];
const receipt = { schema: 'probity-root-site-browser-check/v1', valid: false,
  scope: 'Author browser checks; no unfamiliar-human result, corpus execution or outside adoption.',
  tasks: [], viewports: [], network: [] };
const server = createServer((request, response) => {
  if (request.url === '/' || request.url === '/index.html') {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    response.end(html);
  } else { response.writeHead(404); response.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const local = `http://127.0.0.1:${server.address().port}/`;
const log = createWriteStream(join(out, 'chrome.log'));
const browser = spawn(process.env.CHROME_BIN ?? 'google-chrome', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--remote-debugging-port=0',
  `--user-data-dir=${profile}`, 'about:blank',
], { stdio: ['ignore', 'pipe', 'pipe'] });
browser.stdout.pipe(log, { end: false });
browser.stderr.pipe(log, { end: false });
let browserError;
browser.on('error', error => { browserError = error; });
let socket;
let sequence = 0;
const pending = new Map();
const responses = new Map();
const commands = [];

function browserAlive() {
  return Boolean(browser.pid) && browser.exitCode === null && browser.signalCode === null;
}

async function waitForBrowserExit(milliseconds) {
  if (!browserAlive()) return;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), milliseconds);
  try { await once(browser, 'exit', { signal: controller.signal }); }
  catch (error) { if (error.name !== 'AbortError') throw error; }
  finally { clearTimeout(timer); }
}

async function stopBrowser() {
  if (!browserAlive()) return;
  let wait = waitForBrowserExit(5_000);
  browser.kill('SIGTERM');
  await wait;
  if (!browserAlive()) return;
  wait = waitForBrowserExit(5_000);
  browser.kill('SIGKILL');
  await wait;
  if (browserAlive()) throw new Error('Chrome did not stop after SIGKILL');
}

function rejectCommands(error) {
  for (const item of pending.values()) { clearTimeout(item.timer); item.reject(error); }
  pending.clear();
}

browser.on('exit', (code, signal) => rejectCommands(new Error(`Chrome stopped (exit=${code}, signal=${signal})`)));

async function openSocket(url) {
  const connection = new WebSocket(url);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => fail(new Error('CDP WebSocket open timeout')), 10_000);
    function clear() {
      clearTimeout(timer);
      connection.removeEventListener('open', opened);
      connection.removeEventListener('error', failed);
      connection.removeEventListener('close', closed);
    }
    function fail(error) { clear(); connection.close(); reject(error); }
    function opened() { clear(); resolve(); }
    function failed() { fail(new Error('CDP WebSocket failed before open')); }
    function closed() { fail(new Error('CDP WebSocket closed before open')); }
    connection.addEventListener('open', opened);
    connection.addEventListener('error', failed);
    connection.addEventListener('close', closed);
  });
  connection.addEventListener('close', () => rejectCommands(new Error('CDP WebSocket closed')));
  connection.addEventListener('error', () => rejectCommands(new Error('CDP WebSocket failed')));
  return connection;
}

async function until(check, label) {
  const end = Date.now() + 30_000;
  while (Date.now() < end) {
    const value = await check();
    if (value) return value;
    await delay(100);
  }
  throw new Error(`Timed out: ${label}`);
}

function cdp(method, params = {}) {
  if (!browserAlive()) throw new Error(`Chrome stopped (exit=${browser.exitCode}, signal=${browser.signalCode})`);
  if (socket.readyState !== WebSocket.OPEN) throw new Error('CDP WebSocket is not open');
  const id = ++sequence;
  commands.push({ id, method, params });
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 30_000);
    pending.set(id, { resolve, reject, timer });
    try { socket.send(JSON.stringify({ id, method, params })); }
    catch (error) { pending.delete(id); clearTimeout(timer); reject(error); }
  });
}

async function evaluate(expression) {
  const result = await cdp('Runtime.evaluate', { expression, returnByValue: true });
  assert(!result.exceptionDetails, JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

async function navigate(url) {
  await cdp('Page.navigate', { url });
  await until(async () => {
    const state = await evaluate('({url:location.href,ready:document.readyState})');
    return state.url === url && state.ready === 'complete';
  }, `page ${url}`);
}

async function key(name, code) {
  for (const type of ['keyDown', 'keyUp']) {
    await cdp('Input.dispatchKeyEvent', { type, key: name, code: name, windowsVirtualKeyCode: code });
  }
}

async function focus() {
  return evaluate(`(() => {const a=document.activeElement,r=a.getBoundingClientRect(),s=getComputedStyle(a);
    const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
    const context=canvas.getContext('2d');
    const rgba=color=>{context.clearRect(0,0,1,1);context.fillStyle=color;context.fillRect(0,0,1,1);return [...context.getImageData(0,0,1,1).data];};
    let opacity=1;const backgrounds=[];
    for(let node=a;node;node=node.parentElement){const style=getComputedStyle(node);opacity*=Number(style.opacity);backgrounds.unshift(rgba(style.backgroundColor));}
    return {
    text:a.textContent.trim(),href:a.getAttribute('href'),left:r.left,top:r.top,right:r.right,bottom:r.bottom,
    outline:s.outlineStyle,outlineWidth:s.outlineWidth,outlineColor:s.outlineColor,
    outlineRGBA:rgba(s.outlineColor),backgrounds,effectiveOpacity:opacity,visibility:s.visibility};})()`);
}

function focusContrast(item) {
  const blend = (foreground, background, alpha) => foreground.slice(0, 3).map((value, index) => value * alpha + background[index] * (1 - alpha));
  let background = [255, 255, 255];
  for (const color of item.backgrounds) background = blend(color, background, color[3] / 255);
  const outline = blend(item.outlineRGBA, background, item.outlineRGBA[3] / 255 * item.effectiveOpacity);
  const luminance = color => color.map(value => value / 255).map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
  const first = luminance(background), second = luminance(outline);
  return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
}

try {
  const port = await until(async () => {
    if (browserError) throw browserError;
    if (!browserAlive()) throw new Error(`Chrome stopped (exit=${browser.exitCode}, signal=${browser.signalCode})`);
    try { return (await readFile(join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0]; }
    catch (error) { if (error.code !== 'ENOENT') throw error; return null; }
  }, 'Chrome debug port');
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json`, { signal: AbortSignal.timeout(10_000) })).json();
  socket = await openSocket(tabs.find(tab => tab.type === 'page').webSocketDebuggerUrl);
  socket.addEventListener('message', event => {
    let message;
    try { message = JSON.parse(event.data); }
    catch { rejectCommands(new Error('CDP WebSocket returned malformed JSON')); socket.close(); return; }
    if (message.id) {
      const item = pending.get(message.id);
      if (!item) return;
      pending.delete(message.id); clearTimeout(item.timer);
      if (message.error) item.reject(new Error(JSON.stringify(message.error)));
      else item.resolve(message.result);
    } else if (message.method === 'Network.requestWillBeSent') {
      receipt.network.push(message.params.request.url);
    } else if (message.method === 'Network.responseReceived') {
      responses.set(message.params.response.url, message.params.response.status);
    }
  });
  await cdp('Page.enable');
  await cdp('Network.enable');
  receipt.browser = await cdp('Browser.getVersion');
  for (const width of [1280, 390]) {
    await cdp('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 500 });
    await navigate(local);
    const layout = await evaluate(`({width:innerWidth,content:document.documentElement.scrollWidth,
      lang:document.documentElement.lang,title:document.title,
      scripts:document.scripts.length,stylesheets:document.querySelectorAll('link[rel="stylesheet"]').length})`);
    assert.equal(layout.lang, 'en');
    assert(layout.title.trim());
    assert(layout.content <= layout.width, `Horizontal overflow at ${width}: ${JSON.stringify(layout)}`);
    assert.equal(layout.scripts, 0, 'Root page must remain a static entry');
    assert.equal(layout.stylesheets, 0, 'Root page must not fetch a stylesheet');
    const ax = await cdp('Accessibility.getFullAXTree');
    await writeFile(join(out, `accessibility-${width}.json`), JSON.stringify(ax, null, 2));
    assert(ax.nodes.some(node => node.role?.value === 'main' && !node.ignored), 'Accessible main landmark missing');
    for (const [label] of tasks) assert(ax.nodes.some(node => node.role?.value === 'link' && node.name?.value === label && !node.ignored), `Accessible task missing: ${label}`);
    await key('Tab', 9);
    const skip = await focus();
    assert.equal(skip.text, 'Skip to content');
    assert(skip.href?.startsWith('#') && skip.top >= 0, 'Keyboard skip link must be visible');
    await key('Enter', 13);
    assert.equal(await evaluate('document.activeElement.tagName'), 'MAIN', 'Skip link must move focus to main');
    const links = [];
    for (const [label, href] of tasks) {
      await key('Tab', 9);
      const item = await focus();
      assert.equal(item.text, label); assert.equal(item.href, href);
      assert(item.outline !== 'none' && parseFloat(item.outlineWidth) > 0, `Visible keyboard focus missing: ${label}`);
      item.contrast = focusContrast(item);
      assert(item.visibility === 'visible' && item.contrast >= 3 && item.right > item.left && item.bottom > item.top,
        `Keyboard focus is not visibly painted: ${label} (contrast=${item.contrast})`);
      assert(item.left >= 0 && item.right <= width, `Focused link outside viewport: ${label}`);
      links.push(item);
    }
    const screenshot = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    await writeFile(join(out, `root-${width}.png`), Buffer.from(screenshot.data, 'base64'));
    receipt.viewports.push({ ...layout, skip, keyboard: links });
  }
  assert(receipt.network.every(url => url.startsWith(local)), 'Root entry loaded an external dependency');
  for (let index = 0; index < tasks.length; index++) {
    const [label, href] = tasks[index];
    await navigate(local); await key('Tab', 9); await key('Enter', 13);
    for (let tab = 0; tab <= index; tab++) await key('Tab', 9);
    assert.equal((await focus()).text, label);
    await key('Enter', 13);
    await until(async () => {
      const state = await evaluate('({url:location.href,ready:document.readyState})');
      return state.url === href && state.ready === 'complete';
    }, `keyboard destination ${label}`);
    assert.equal(responses.get(href), 200, `Destination failed: ${href}`);
    const page = await evaluate('({url:location.href,title:document.title,text:document.body.innerText,commands:[...document.querySelectorAll("pre")].map(p=>p.textContent)})');
    assert(page.title.trim() && page.text.length > 200, `Task destination has no usable content: ${label}`);
    if (index === 0) {
      assert(page.commands.some(command => /agent-evidence-vectors==\d+\.\d+\.\d+/.test(command)), 'Verifier task lacks a pinned Python install');
      assert(page.commands.some(command => /aee-verify@v\d+\.\d+\.\d+/.test(command)), 'Verifier task lacks a pinned Go install');
      assert(/Python 3\.\d+\+/.test(page.text) && /Go 1\.\d+\+/.test(page.text), 'Verifier prerequisites are missing');
    } else if (index === 2) {
      const components = ['vectors', 'verify', 'admission', 'observer', 'vocabulary', 'atlas', 'jcs-admit', 'dsse'];
      assert(await evaluate(`${JSON.stringify(components)}.every(id => document.getElementById(id))`), 'Component catalog must expose all eight components');
    }
    await writeFile(join(out, `task-${index + 1}.html`), await evaluate('document.documentElement.outerHTML'));
    receipt.tasks.push({ label, url: page.url, status: responses.get(href), title: page.title });
  }
  receipt.valid = true;
} catch (error) {
  receipt.error = error.stack;
  process.exitCode = 1;
} finally {
  await writeFile(join(out, 'RESULTS.json'), JSON.stringify(receipt, null, 2) + '\n');
  await writeFile(join(out, 'cdp-commands.json'), JSON.stringify(commands, null, 2) + '\n');
  socket?.close();
  await stopBrowser();
  await new Promise(resolve => server.close(resolve));
  log.end();
  await rm(profile, { recursive: true, force: true });
}
console.log(JSON.stringify(receipt, null, 2));
