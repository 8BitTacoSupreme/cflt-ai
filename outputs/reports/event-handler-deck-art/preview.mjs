// Rasterises the SVG art to PNG for visual review. Not part of the deliverable —
// the SVGs are what goes in the deck; this just lets us look at them.
import puppeteer from '/Users/jhogan/.npm/_npx/d62b6517736c1e35/node_modules/puppeteer/lib/puppeteer/puppeteer.js';
import { readdirSync, readFileSync, mkdirSync } from 'node:fs';
import { join, dirname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const svgDir = join(here, 'svg');
const outDir = join(here, 'png');
mkdirSync(outDir, { recursive: true });

const only = process.argv.slice(2);
const files = readdirSync(svgDir)
  .filter(f => f.endsWith('.svg'))
  .filter(f => only.length === 0 || only.some(o => f.includes(o)));

const browser = await puppeteer.launch({ headless: 'new' });
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 1 });

for (const f of files) {
  const svg = readFileSync(join(svgDir, f), 'utf8');
  await page.setContent(
    `<html><body style="margin:0;background:#fff">${svg}</body></html>`,
    { waitUntil: 'load' }
  );
  const el = await page.$('svg');
  await el.screenshot({ path: join(outDir, basename(f, '.svg') + '.png') });
  console.log('rendered', f);
}

await browser.close();
