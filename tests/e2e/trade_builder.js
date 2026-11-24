// ABOUTME: The trade builder typeahead lists clubs in order, draws one roster, and posts what each club sends.
// ABOUTME: Usage: CHROME_PATH=/usr/local/bin/google-chrome node tests/e2e/trade_builder.js
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const include = fs.readFileSync(
  path.join(__dirname, '../../ulmg/templates/includes/trade_builder_script.html'),
  'utf8'
);
const styleOpen = include.indexOf('<style>');
const scriptClose = include.lastIndexOf('</script>');
if (styleOpen < 0 || scriptClose < 0) {
  throw new Error('trade_builder_script.html has no style and script');
}
const widget = include.slice(styleOpen, scriptClose + '</script>'.length);

function club(side) {
  return `<section data-side="${side}">
    <h2 data-heading>Club ${side}</h2>
    <div>
      <select id="team-${side}-select" data-trade-team aria-label="Club ${side}">
        <option value="">Select team</option>
        <option value="alb">Albany Aces (ALB)</option>
        <option value="zzz">Boston Ants (ZZZ)</option>
        <option value="aaa">Boston Zebras (AAA)</option>
        <option value="cin">Cincinnati Cubs (CIN)</option>
      </select>
    </div>
    <input data-roster-filter aria-label="Filter club ${side}">
    <p data-sending>Sends nothing yet.</p>
    <p data-empty>Pick a club to see who they can send.</p>
    <div data-group="hitters"><div data-kind="hitters"></div></div>
    <div data-group="pitchers"><div data-kind="pitchers"></div></div>
    <div data-group="picks"><div data-kind="picks"></div></div>
  </section>`;
}

const assets = {
  alb: {
    hitters: [
      {id: 'player-1', label: 'IF Ada Infielder · V · block'},
      {id: 'player-2', label: 'OF Oscar Outfielder · A'}
    ],
    pitchers: [],
    picks: []
  },
  cin: {
    hitters: [],
    pitchers: [{id: 'player-9', label: 'P Abe Pitcher · A'}],
    picks: [{id: 'pick-4', label: '2027 offseason CIN OP1'}]
  },
  zzz: {hitters: [], pitchers: [], picks: []},
  aaa: {hitters: [], pitchers: [], picks: []}
};

const html = `<!DOCTYPE html><html><body>
  <p id="trade-summary"></p>
  <p id="trade-status" role="status"></p>
  <button id="trade-submit" type="button">Submit Trade</button>
  ${club(1)}
  ${club(2)}
  <script id="trade-assets" type="application/json">${JSON.stringify(assets)}</script>
  ${widget}
</body></html>`;

function fail(message) {
  throw new Error(message);
}

(async () => {
  const launch = {headless: true};
  if (process.env.CHROME_PATH) {
    launch.executablePath = process.env.CHROME_PATH;
    launch.args = ['--no-sandbox', '--disable-dev-shm-usage'];
  }
  const browser = await chromium.launch(launch);
  const page = await browser.newPage();
  await page.setContent(html);
  await page.evaluate(() => {
    window.__posts = [];
    window.__fetchResult = {success: false};
    window.fetch = async (url, opts) => {
      window.__posts.push({
        url: url,
        body: opts.body,
        type: opts.headers['Content-Type']
      });
      return {json: async () => window.__fetchResult};
    };
    location.reload = () => {};
  });

  const clubs = page.locator('[role="combobox"]');
  if (await page.locator('#team-1-select').isVisible()) fail('the club select is replaced by the typeahead');
  if ((await clubs.count()) !== 2) fail('each club gets a typeahead');
  if ((await clubs.nth(0).getAttribute('aria-label')) !== 'Club 1') fail('the first box keeps the Club 1 label');

  await clubs.nth(0).focus();
  const open = page.locator('[role="listbox"]:visible [role="option"]');
  const names = await open.allInnerTexts();
  if (names.join('|') !== 'Albany Aces (ALB)|Boston Ants (ZZZ)|Boston Zebras (AAA)|Cincinnati Cubs (CIN)') {
    fail('focus lists the clubs in alphabetical order, got ' + names.join('|'));
  }

  await clubs.nth(0).fill('bos');
  const boston = await open.allInnerTexts();
  if (boston.join('|') !== 'Boston Ants (ZZZ)|Boston Zebras (AAA)') {
    fail('typing a city filters to those clubs, got ' + boston.join('|'));
  }

  await clubs.nth(0).fill('zzz');
  await clubs.nth(0).press('Enter');
  if ((await page.locator('#team-1-select').inputValue()) !== 'zzz') fail('enter files the highlighted club');
  if ((await page.locator('[data-side="1"] [data-empty]').innerText()) !== 'Nobody to send.') {
    fail('an empty club says nobody to send');
  }
  if (await page.locator('[data-side="1"] [data-group="hitters"]').isVisible()) {
    fail('an empty club hides the hitter list');
  }

  await page.locator('#trade-submit').click();
  if ((await page.locator('#trade-status').innerText()) !== 'Pick both clubs.') fail('submit asks for both clubs');
  if ((await page.evaluate(() => window.__posts.length)) !== 0) fail('an incomplete trade is not posted');

  await clubs.nth(0).fill('alb');
  await clubs.nth(0).press('Enter');
  const hitters = page.locator('[data-side="1"] [data-kind="hitters"] .player-option');
  if ((await hitters.count()) !== 2) fail('picking Albany draws only that roster');
  if (await page.locator('[data-side="1"] [data-group="pitchers"]').isVisible()) {
    fail('a club with no pitchers hides that list');
  }
  if ((await hitters.nth(0).innerText()) !== 'IF Ada Infielder · V · block') fail('the block mark stays on the hitter');

  const oscar = page.locator('[data-side="1"] .player-option', {hasText: 'Oscar'});
  await oscar.click();
  if (!(await oscar.evaluate((el) => el.classList.contains('is-sending')))) fail('clicking a player marks him as sent');

  await clubs.nth(0).fill('aaa');
  await clubs.nth(0).press('Enter');
  if ((await page.locator('[data-side="1"] .player-option.is-sending').count()) !== 0) {
    fail('switching clubs clears who they were sending');
  }

  await clubs.nth(0).fill('alb');
  await clubs.nth(0).press('Enter');
  await oscar.click();
  await page.locator('[data-side="1"] [data-roster-filter]').fill('ada');
  if (await oscar.isVisible()) fail('the roster filter hides players who do not match');
  if (!(await page.locator('[data-side="1"] .player-option', {hasText: 'Ada'}).isVisible())) {
    fail('the roster filter keeps the matching player');
  }
  if ((await page.locator('[data-side="1"] [data-sending]').innerText()) !== 'Sends OF Oscar Outfielder · A') {
    fail('a filtered-out player stays in the sends line');
  }

  await clubs.nth(1).focus();
  const second = await open.allInnerTexts();
  if (second.indexOf('Albany Aces (ALB)') !== -1) fail('the other box does not offer the club already picked');
  if (second[0] !== 'Boston Ants (ZZZ)') fail('the other box still starts in alphabetical order');

  await clubs.nth(1).fill('cin');
  await open.first().click();
  if ((await page.locator('#team-2-select').inputValue()) !== 'cin') fail('clicking a club files it');
  if ((await page.locator('[data-side="2"] .player-option', {hasText: 'Ada'}).count()) !== 0) {
    fail('club 2 does not draw Albany players');
  }
  await page.locator('[data-side="2"] .player-option', {hasText: 'OP1'}).click();

  const summary = await page.locator('#trade-summary').innerText();
  if (summary !== 'Albany Aces (ALB) sends OF Oscar Outfielder · A to Cincinnati Cubs (CIN) for 2027 offseason CIN OP1') {
    fail('the summary names what each club sends, got ' + summary);
  }

  await page.locator('#trade-submit').click();
  if ((await page.locator('#trade-status').innerText()) !== 'Trade did not save.') fail('a failed save is shown');
  if (await page.locator('#trade-submit').isDisabled()) fail('a failed save can be tried again');

  const posted = await page.evaluate(() => window.__posts);
  if (posted.length !== 1) fail('the trade was posted once');
  if (posted[0].url !== '/api/v1/trade/bulk/') fail('the trade posts to the bulk endpoint');
  if (posted[0].type !== 'application/x-www-form-urlencoded; charset=UTF-8') fail('the body is posted the way the bulk endpoint reads it');
  if (posted[0].body !== '[{"team":"alb","receipt":["player-2"]},{"team":"cin","receipt":["pick-4"]}]') {
    fail('the receipt is who each club sends, got ' + posted[0].body);
  }

  await page.evaluate(() => { window.__fetchResult = {success: true}; });
  await page.locator('#trade-submit').click();
  if ((await page.locator('#trade-status').innerText()) !== 'Trade submitted. Reloading.') fail('a saved trade tells you it is reloading');
  if ((await page.locator('#trade-submit').count()) !== 0) fail('the submit button goes away after a save');

  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
