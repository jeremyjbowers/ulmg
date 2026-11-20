// ABOUTME: Checking Unlimited on a depth-chart form clears the number and keeps it from being submitted.
// ABOUTME: Usage: node tests/e2e/depth_chart.js
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const template = fs.readFileSync(
  path.join(__dirname, '../../ulmg/templates/includes/depth_script.html'),
  'utf8'
);
const scriptOpen = template.indexOf('<script>');
const scriptClose = template.lastIndexOf('</script>');
if (scriptOpen < 0 || scriptClose < 0) {
  throw new Error('depth_script.html has no script block');
}
const script = template.slice(scriptOpen + '<script>'.length, scriptClose);

function form(id, amount, checked) {
  const mark = checked ? ' checked' : '';
  return `<form id="${id}" data-depth-form>
    <input type="number" name="amount" data-amount value="${amount}">
    <input type="checkbox" name="unlimited" data-unlimited${mark}>
  </form>`;
}

const html = `<!DOCTYPE html><html><body>
  ${form('add', '200', false)}
  ${form('already', '40', true)}
  <form id="remove"><input type="number" name="amount" value="9"></form>
</body></html>`;

(async () => {
  const launch = { headless: true };
  if (process.env.CHROME_PATH) {
    launch.executablePath = process.env.CHROME_PATH;
    launch.args = ["--no-sandbox", "--disable-dev-shm-usage"];
  }
  const browser = await chromium.launch(launch);
  const page = await browser.newPage();
  await page.setContent(html);
  await page.addScriptTag({ content: script });

  const add = page.locator('#add [data-amount]');
  const box = page.locator('#add [data-unlimited]');
  if (await add.isDisabled()) throw new Error('a numbered row starts with the amount editable');
  if ((await add.inputValue()) !== '200') throw new Error('a numbered row keeps its amount');

  await box.check();
  if (!(await add.isDisabled())) throw new Error('unlimited disables the amount');
  if ((await add.inputValue()) !== '') throw new Error('unlimited clears the amount so it is not submitted');

  await box.uncheck();
  if (await add.isDisabled()) throw new Error('unchecking unlimited makes the amount editable again');

  const already = page.locator('#already [data-amount]');
  if (!(await already.isDisabled())) throw new Error('a row that is already unlimited loads with the amount disabled');
  if ((await already.inputValue()) !== '') throw new Error('a row that is already unlimited loads with the amount cleared');

  const remove = page.locator('#remove [name="amount"]');
  if (await remove.isDisabled()) throw new Error('a form without the checkbox is left alone');
  if ((await remove.inputValue()) !== '9') throw new Error('a form without the checkbox keeps its amount');

  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
