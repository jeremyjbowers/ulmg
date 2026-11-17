// ABOUTME: A full MLB roster hides add buttons in the page; sending one player to AAA shows them again.
// ABOUTME: Usage: node tests/e2e/roster_cap.js
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const template = fs.readFileSync(
  path.join(__dirname, '../../ulmg/templates/includes/player_protect_actions_script.html'),
  'utf8'
);
const scriptOpen = template.indexOf('<script>');
const scriptClose = template.lastIndexOf('</script>');
if (scriptOpen < 0 || scriptClose < 0) {
  throw new Error('player_protect_actions_script.html has no script block');
}
const script = template.slice(scriptOpen + '<script>'.length, scriptClose);

const html = `<!DOCTYPE html>
<html><body>
<span id="roster-mlb-count">30</span>
<div id="drop-modal" class="hidden" data-mlb-roster-count="30" data-mlb-roster-size="30"></div>
<table>
  <tr id="on-mlb">
    <td>
      <a class="player-action" data-playerid="1" data-roster="mlb" data-action="off_roster">MLB</a>
      <a class="player-action" data-playerid="1" data-roster="aaa" data-action="to_aaa">AAA</a>
    </td>
  </tr>
  <tr id="waiting">
    <td>
      <a class="player-action hidden" style="display:none" data-playerid="2" data-roster="mlb" data-action="to_mlb">MLB</a>
      <a class="player-action" data-playerid="2" data-roster="aaa" data-action="off_roster">AAA</a>
    </td>
  </tr>
  <tr id="also-full">
    <td>
      <a class="player-action" data-playerid="3" data-roster="mlb" data-action="off_roster">MLB</a>
      <a class="player-action" data-playerid="3" data-roster="aaa" data-action="to_aaa">AAA</a>
    </td>
  </tr>
</table>
<script>window.$ = { ajax: function (opts) { opts.success('ok'); } };</script>
<script>${script}</script>
</body></html>`;

function visible(page, selector) {
  return page.locator(selector).evaluate((el) => {
    const style = window.getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  });
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  const failures = [];
  page.on('pageerror', (error) => failures.push(String(error)));
  await page.setContent(html);
  await page.waitForFunction(() => document.querySelector('#waiting [data-action="to_mlb"]').style.display === 'none');

  if (await visible(page, '#waiting [data-action="to_mlb"]')) {
    failures.push('MLB add button was visible at 30/30');
  }

  await page.click('#on-mlb [data-action="to_aaa"]');
  await page.waitForFunction(() => document.getElementById('roster-mlb-count').textContent === '29');

  if (!(await visible(page, '#waiting [data-action="to_mlb"]'))) {
    failures.push('MLB add button stayed hidden after a player moved to AAA');
  }
  const waitingAction = await page.locator('#waiting [data-roster="mlb"]').getAttribute('data-action');
  if (waitingAction !== 'to_mlb') failures.push(`waiting MLB action is ${waitingAction}`);
  const movedAction = await page.locator('#on-mlb [data-roster="mlb"]').getAttribute('data-action');
  if (movedAction !== 'to_mlb') failures.push(`moved player MLB action is ${movedAction}`);
  if (!(await visible(page, '#on-mlb [data-roster="mlb"]'))) {
    failures.push('the player sent to AAA lost his MLB button');
  }

  await page.click('#waiting [data-action="to_mlb"]');
  await page.waitForFunction(() => document.getElementById('roster-mlb-count').textContent === '30');
  if (await visible(page, '#on-mlb [data-action="to_mlb"]')) {
    failures.push('MLB add buttons stayed visible once the roster was full again');
  }
  const placed = await page.locator('#waiting [data-roster="mlb"]').getAttribute('data-action');
  if (placed !== 'off_roster') failures.push(`placed player action is ${placed}`);

  await page.click('#also-full [data-action="off_roster"]');
  await page.waitForFunction(() => document.getElementById('roster-mlb-count').textContent === '29');
  if (!(await visible(page, '#on-mlb [data-action="to_mlb"]'))) {
    failures.push('MLB add button stayed hidden after a player left the MLB roster');
  }

  await browser.close();
  if (failures.length) {
    console.error(failures.join('\n'));
    process.exit(1);
  }
  console.log('ok  a full MLB roster shows add buttons again after a player moves to AAA');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
