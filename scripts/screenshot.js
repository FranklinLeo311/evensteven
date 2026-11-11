/* Screenshot a page of the running app at phone and desktop width. Usage: node screenshot.js <path> <name> */
const path = require('path');
const { chromium } = require('C:/Azure-Devops/Automation_Testing/IncomeCalculator-Automation-Testing/node_modules/playwright');
const [route = '/', name = 'home'] = process.argv.slice(2);
(async () => {
  const browser = await chromium.launch();
  for (const width of [390, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto('http://localhost:8090' + route, { waitUntil: 'networkidle' });
    await page.screenshot({ path: path.join(__dirname, 'shots', `${name}_${width}.png`), fullPage: true });
    await page.close();
  }
  await browser.close();
})();
