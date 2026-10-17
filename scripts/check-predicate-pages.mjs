// Refuses a change to a published predicate page. A predicate type URI never
// moves once a signed statement carries it, so each page is pinned by digest
// in probity/predicate/v1/PAGES.sha256 and the page must name its own URI.
import { readFile, readdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

const dir = 'probity/predicate/v1';
const base = 'https://probityai.github.io/probity/predicate/v1/';
const pinned = new Map((await readFile(join(dir, 'PAGES.sha256'), 'utf8')).trim().split('\n')
  .map((l) => l.split('  ').reverse()));
const slugs = (await readdir(dir, { withFileTypes: true })).filter((d) => d.isDirectory()).map((d) => d.name);
const failures = [];
for (const slug of slugs) {
  const bytes = await readFile(join(dir, slug, 'index.html'));
  const text = bytes.toString('utf8');
  const digest = createHash('sha256').update(bytes).digest('hex');
  if (!pinned.has(slug)) failures.push(`${slug}: not listed in PAGES.sha256`);
  else if (pinned.get(slug) !== digest) failures.push(`${slug}: published page changed (digest ${digest})`);
  if (!text.includes(`<link rel="canonical" href="${base}${slug}">`)) failures.push(`${slug}: canonical link is not its type URI`);
}
for (const slug of pinned.keys()) if (!slugs.includes(slug)) failures.push(`${slug}: pinned page is missing`);
if (failures.length) { console.error(failures.join('\n')); process.exit(1); }
console.log(`predicate pages ok: ${slugs.length}`);
