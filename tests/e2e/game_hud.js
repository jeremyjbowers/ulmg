// ABOUTME: End-to-end check of the game HUD in a real browser: plays plate appearances on a seeded game served by runserver.
// ABOUTME: Usage: node tests/e2e/game_hud.js <base url> <game id> <session key> <compiled tailwind css> <screenshot dir>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [, , base, gameId, sessionKey, cssPath, outDir] = process.argv;
if (!outDir) {
  console.error('usage: node tests/e2e/game_hud.js <base url> <game id> <session key> <tailwind css> <screenshot dir>');
  process.exit(2);
}
const css = fs.readFileSync(cssPath, 'utf8');
const url = `${base}/games/${gameId}/`;
const failures = [];

function check(ok, message) {
  if (!ok) failures.push(message);
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${message}`);
}

async function context(browser, width, height, colorScheme = 'light') {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, colorScheme });
  const host = new URL(base).hostname;
  await ctx.addCookies([{ name: 'sessionid', value: sessionKey, domain: host, path: '/' }]);
  // The Tailwind CDN is unreachable here: answer it with the locally compiled stylesheet.
  await ctx.route(/cdn\.tailwindcss\.com/, (route) => route.fulfill({
    status: 200,
    contentType: 'text/javascript',
    // The site header's menus need the CDN's in-browser build, so it is hidden, as in the earlier game page screenshots.
    body: `document.head.insertAdjacentHTML('beforeend', ${JSON.stringify(`<style>${css} header{display:none!important} .content-with-fixed-header{padding-top:8px!important}</style>`)});`,
  }));
  await ctx.route((u) => !u.href.startsWith(base) && !/cdn\.tailwindcss\.com/.test(u.href), (route) => route.fulfill({ status: 204, body: '' }));
  const page = await ctx.newPage();
  page.on('pageerror', (error) => failures.push(`page error: ${error}`));
  page.on('console', (msg) => { if (msg.type() === 'error' && !/Failed to load resource|SW reg failed/.test(msg.text())) failures.push(`console: ${msg.text()}`); });
  return page;
}

async function shot(page, name) {
  const file = path.join(outDir, `${name}.png`);
  await page.screenshot({ path: file });
  console.log(`     saved ${file}`);
}

async function resolveNeed(page) {
  // A forced change opens its tab by itself: take the first legal player and confirm.
  const drawer = page.locator('.hud-drawer.open');
  if (!(await drawer.count())) return false;
  await drawer.locator('tr.row').first().click();
  await Promise.all([page.waitForNavigation(), drawer.locator('[data-confirm]').click()]);
  return true;
}

async function play(page, { settle = 2600 } = {}) {
  const button = page.locator('#hud-play');
  if (await button.isDisabled()) {
    if (await resolveNeed(page)) return play(page, { settle });
    throw new Error(`Play is disabled: ${await page.locator('.hud-playdock .hud-why').textContent()}`);
  }
  await Promise.all([page.waitForNavigation(), button.click()]);
  await page.waitForTimeout(settle);
}

async function openTab(page, tab) {
  await page.evaluate((key) => {
    document.querySelectorAll('.hud-drawer').forEach((d) => d.classList.toggle('open', d.getAttribute('data-tab') === key));
  }, tab);
  await page.waitForTimeout(350);
  const drawer = page.locator(`#sub-${tab}`);
  const row = drawer.locator('tr.row').first();
  if (await row.count()) {
    await row.click();
    const compare = (await drawer.locator('[data-compare-text]').textContent()) || '';
    check(!/Pick a player/.test(compare), `${tab}: picking a row fills the comparison line ("${compare.trim().slice(0, 80)}")`);
  }
  return drawer;
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();

  // Desktop.
  const page = await context(browser, 1320, 900);
  await page.goto(url);
  await page.evaluate(() => { try { localStorage.setItem('ulmg-hud-fast', '0'); } catch (e) {} });
  await page.reload();
  await page.waitForTimeout(2500);
  check(await page.locator('.hud-board').isVisible(), 'the scoreboard is on the page');
  check((await page.locator('#hud-fielders .fielder').count()) === 9, 'nine fielders are drawn');
  check(/[+−]\d\.\d/.test(await page.locator('#hud-fielders').textContent()), 'fielders carry ratings in runs');
  await shot(page, 'desktop_start');

  // Plate appearances until a hit leaves runners on, catching one mid-animation.
  let midTaken = false;
  let hitTaken = false;
  for (let i = 0; i < 30 && !hitTaken; i++) {
    const button = page.locator('#hud-play');
    if (await button.isDisabled()) { if (await resolveNeed(page)) continue; break; }
    await Promise.all([page.waitForNavigation(), page.keyboard.press('Space')]);
    if (!midTaken) {
      await page.waitForTimeout(700);
      await shot(page, 'desktop_mid_animation');
      check(await page.locator('#hud-banner.show').count() + await page.locator('#hud-ball').evaluate((b) => Number(getComputedStyle(b).opacity) > 0 ? 1 : 0) > 0, 'the play animates: the ball or the banner is showing');
      midTaken = true;
    }
    await page.waitForTimeout(2600);
    const banner = (await page.locator('#hud-banner-big').textContent()) || '';
    const runners = await page.locator('#hud-runners .runner').count();
    if (/SINGLE|DOUBLE|TRIPLE|ERROR|BUNT HIT|WALK/.test(banner) && runners > 0) {
      await page.waitForTimeout(400);
      await shot(page, 'desktop_hit_runners_on');
      check(/Speed \d\.\d/.test(await page.locator('#hud-runners').textContent()), 'runners show their speed');
      hitTaken = true;
    }
  }
  check(hitTaken, 'a hit put runners on base');

  // The substitution panel, tab by tab.
  for (const tab of ['ph', 'pr', 'pit', 'def']) {
    await openTab(page, tab);
    await shot(page, `desktop_panel_${tab}`);
  }
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  check(!(await page.locator('.hud-drawer.open').count()), 'Esc closes the panel');
  check(/\d+% \([+−±]\d+\)/.test(await page.locator('#sub-ph').textContent()), 'pinch hitters show their chance to reach base');

  // Fast skips the animation, and the choice is remembered.
  await page.check('#hud-fast');
  await play(page, { settle: 300 });
  check(await page.locator('#hud-fast').isChecked(), 'Fast is remembered across the reload');
  check(!(await page.locator('#hud-banner.show').count()), 'Fast shows no animation');
  await page.uncheck('#hud-fast');

  // Phone.
  const phone = await context(browser, 390, 844);
  await phone.goto(url);
  await phone.evaluate(() => { try { localStorage.setItem('ulmg-hud-fast', '0'); } catch (e) {} });
  await phone.reload();
  await phone.waitForTimeout(2500);
  await shot(phone, 'phone_start');
  const field = await phone.locator('#hud-field').boundingBox();
  const batterCard = await phone.locator('.hud-batter').boundingBox();
  check(field.y < batterCard.y, 'on a phone the field comes before the cards');
  const dock = await phone.locator('.hud-playdock').evaluate((d) => getComputedStyle(d).position);
  check(dock === 'fixed', 'on a phone Play is pinned to the bottom');
  const small = await phone.locator('.hud-btn:visible').evaluateAll((buttons) => buttons.filter((b) => b.getBoundingClientRect().height < 44).length);
  check(small === 0, 'every visible button is at least 44px tall');
  const button = phone.locator('#hud-play');
  if (!(await button.isDisabled())) {
    await Promise.all([phone.waitForNavigation(), button.click()]);
    await phone.waitForTimeout(700);
    await shot(phone, 'phone_mid_animation');
    await phone.waitForTimeout(2600);
  }
  await shot(phone, 'phone_after_play');
  for (const tab of ['ph', 'pr', 'pit', 'def']) {
    await openTab(phone, tab);
    await shot(phone, `phone_panel_${tab}`);
  }

  // Without JavaScript: the panel opens on its anchor and its form posts.
  const plain = await (await browser.newContext({ viewport: { width: 1320, height: 900 }, javaScriptEnabled: false }));
  await plain.addCookies([{ name: 'sessionid', value: sessionKey, domain: new URL(base).hostname, path: '/' }]);
  await plain.route((u) => !u.href.startsWith(base), (route) => route.fulfill({ status: 204, body: '' }));
  const bare = await plain.newPage();
  await bare.goto(url);
  const pinch = bare.locator('a[data-open="ph"].hud-btn');
  if (await pinch.count()) {
    await pinch.click();
    await bare.waitForTimeout(600);
    const box = await bare.locator('#sub-ph').boundingBox();
    check(box && box.x < 1320, 'without JavaScript, Pinch hit opens the panel on its anchor');
    const choice = bare.locator('#sub-ph input[name=player]:not([disabled])').first();
    await choice.check();
    await Promise.all([bare.waitForNavigation(), bare.locator('#sub-ph button[type=submit]').click()]);
    check(/pinch hits for/.test(await bare.locator('.game-play-by-play').textContent()), 'without JavaScript, the pinch-hit form posts and the change is logged');
  }

  // Dark theme.
  const dark = await context(browser, 1320, 900, 'dark');
  await dark.goto(url);
  await dark.waitForTimeout(800);
  const background = await dark.evaluate(() => getComputedStyle(document.body).backgroundColor);
  check(background === 'rgb(20, 20, 15)', `the dark theme darkens the page (${background})`);
  await shot(dark, 'desktop_dark');

  await browser.close();
  if (failures.length) {
    console.log(`\n${failures.length} problem(s):\n${failures.join('\n')}`);
    process.exit(1);
  }
  console.log('\nall checks passed');
})().catch((error) => { console.error(error); process.exit(1); });
