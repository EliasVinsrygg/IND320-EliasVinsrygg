// Printing the self-contained notebook HTML using the previously installed Chromium.
const { chromium } = require('C:/Users/elias/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Users/elias/AppData/Local/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe',
    headless: true,
  });
  try {
    const page = await browser.newPage();
    // Blocking remote assets; notebook attachments and saved plots are embedded.
    await page.route('https://**/*', route => route.abort());
    await page.route('http://**/*', route => route.abort());
    await page.goto(pathToFileURL(path.join(__dirname, 'CA3.html')).href, { waitUntil: 'load' });
    await page.evaluate(async () => {
      await document.fonts.ready;
      await Promise.all([...document.images].map(img => img.decode()));
    });
    const badImages = await page.evaluate(() => [...document.images].filter(img => !img.naturalWidth).length);
    if (badImages) throw new Error(`${badImages} notebook images failed to load`);
    const output = path.resolve(__dirname, '../../../Deliverables/IND320 - CA3 - Elias Vinsrygg.pdf');
    await page.pdf({
      path: output, format: 'A4', preferCSSPageSize: true, printBackground: true,
      displayHeaderFooter: true, headerTemplate: '<span></span>',
      footerTemplate: '<div style="width:100%;text-align:center;font:8px Arial;color:#777"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    });
    console.log(`Created ${output}`);
  } finally {
    await browser.close();
  }
})();
