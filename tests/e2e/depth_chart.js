// ABOUTME: Checking Rest (unlimited) on a playing-time row clears that row's number and keeps it from being submitted.
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

function row(id, amount, checked) {
  const mark = checked ? ' checked' : '';
  return `<tr id="${id}" data-depth-row>
    <td><input type="number" name="amount_${id}" data-amount value="${amount}"></td>
    <td><input type="checkbox" name="unlimited_${id}" data-unlimited${mark}></td>
  </tr>`;
}

const html = `<!DOCTYPE html><html><body>
  <form data-depth-form><table><tbody>
    ${row('add', '200', false)}
    ${row('already', '40', true)}
    <tr id="remove"><td><input type="number" name="amount" value="9"></td></tr>
  </tbody></table></form>
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
  if (await remove.isDisabled()) throw new Error('a row without the checkbox is left alone');
  if ((await remove.inputValue()) !== '9') throw new Error('a row without the checkbox keeps its amount');

  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
