#!/usr/bin/env node
/**
 * Exporta diagramas egon.io (.egn) para SVG usando Puppeteer.
 *
 * Pré-requisitos:
 *   npm install puppeteer
 *
 * Uso:
 *   node scripts/export-egn-to-svg.js
 *   node scripts/export-egn-to-svg.js --egn-dir path/to/egn --out-dir path/to/output
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const os = require('os');

const PROJECT_ROOT = path.resolve(__dirname, '..');

const DEFAULT_EGN_DIR = path.join(PROJECT_ROOT, 'docs/arquitetura/domain-storytelling');
const DEFAULT_OUT_DIR = path.join(PROJECT_ROOT, 'docs/entrega/assets');

const PAGE_LOAD_TIMEOUT_MS = 30000;
const SELECTOR_TIMEOUT_MS = 10000;
const APP_INIT_WAIT_MS = 3000;
const UPLOAD_WAIT_MS = 2000;
const MIN_SVG_LENGTH = 200;

function parseArgs() {
  const args = process.argv.slice(2);
  let egnDir = DEFAULT_EGN_DIR;
  let outDir = DEFAULT_OUT_DIR;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--egn-dir' && args[i + 1]) {
      egnDir = path.resolve(args[++i]);
    } else if (args[i] === '--out-dir' && args[i + 1]) {
      outDir = path.resolve(args[++i]);
    }
  }

  return { egnDir, outDir };
}

async function exportEgn(browser, egnPath, svgPath) {
  const page = await browser.newPage();
  const name = path.basename(egnPath, '.egn');
  console.log(`Processing: ${name}`);

  let tempFile = null;

  try {
    await page.goto('https://egon.io/app', {
      waitUntil: 'networkidle0',
      timeout: PAGE_LOAD_TIMEOUT_MS,
    });
    await page.waitForSelector('body', { timeout: SELECTOR_TIMEOUT_MS });

    const egnContent = fs.readFileSync(egnPath, 'utf-8');

    await new Promise(r => setTimeout(r, APP_INIT_WAIT_MS));

    const fileInput = await page.$('input[type="file"]');

    if (fileInput) {
      tempFile = path.join(os.tmpdir(), `egn-export-${name}-${Date.now()}.egn`);
      fs.writeFileSync(tempFile, egnContent);
      await fileInput.uploadFile(tempFile);
      await new Promise(r => setTimeout(r, UPLOAD_WAIT_MS));
    } else {
      // Fallback: custom event injection
      await page.evaluate((content) => {
        const event = new CustomEvent('importDST', { detail: content });
        document.dispatchEvent(event);
      }, egnContent);
      await new Promise(r => setTimeout(r, UPLOAD_WAIT_MS));
    }

    const svgContent = await page.evaluate(() => {
      const svg = document.querySelector('svg.domain-story-svg')
        || document.querySelector('svg[class*="story"]')
        || document.querySelector('#canvas svg')
        || document.querySelector('.canvas-container svg')
        || document.querySelector('svg');

      if (svg) {
        const clone = svg.cloneNode(true);
        try {
          if (!clone.getAttribute('viewBox')) {
            const bbox = svg.getBBox();
            clone.setAttribute('viewBox', `${bbox.x - 10} ${bbox.y - 10} ${bbox.width + 20} ${bbox.height + 20}`);
          }
        } catch (_) {
          // getBBox can fail on hidden elements
        }
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        return clone.outerHTML;
      }
      return null;
    });

    if (svgContent && svgContent.length > MIN_SVG_LENGTH) {
      fs.writeFileSync(svgPath, svgContent);
      console.log(`  Exported: ${path.basename(svgPath)} (${svgContent.length} bytes)`);
    } else {
      const pngPath = svgPath.replace('.svg', '.png');
      await page.screenshot({ path: pngPath, fullPage: true });
      console.log(`  SVG extraction failed, saved PNG fallback: ${path.basename(pngPath)}`);
    }
  } catch (err) {
    console.error(`  Error processing ${name}: ${err.message}`);
  } finally {
    if (tempFile && fs.existsSync(tempFile)) {
      fs.unlinkSync(tempFile);
    }
    await page.close();
  }
}

async function main() {
  const { egnDir, outDir } = parseArgs();

  if (!fs.existsSync(egnDir)) {
    console.error(`Directory not found: ${egnDir}`);
    process.exit(1);
  }

  const egnFiles = fs.readdirSync(egnDir)
    .filter(f => f.endsWith('.egn'))
    .map(f => path.join(egnDir, f));

  if (egnFiles.length === 0) {
    console.error(`No .egn files found in ${egnDir}`);
    process.exit(1);
  }

  console.log(`Found ${egnFiles.length} .egn files in ${egnDir}`);
  console.log(`Output: ${outDir}\n`);
  fs.mkdirSync(outDir, { recursive: true });

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    for (const egnFile of egnFiles) {
      const svgPath = path.join(outDir, `${path.basename(egnFile, '.egn')}.svg`);
      await exportEgn(browser, egnFile, svgPath);
    }
  } finally {
    if (browser) {
      await browser.close();
    }
  }

  console.log('\nDone!');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
