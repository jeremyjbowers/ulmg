// ABOUTME: Adding a pinch slot, and choosing a starter's hook with buttons, in a real browser.
// ABOUTME: Usage: node tests/e2e/lineup_slots.js
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const template = fs.readFileSync(
  path.join(__dirname, '../../ulmg/templates/includes/card_board_script.html'),
  'utf8'
);
const scriptOpen = template.indexOf('<script>');
const scriptClose = template.lastIndexOf('</script>');
if (scriptOpen < 0 || scriptClose < 0) {
  throw new Error('card_board_script.html has no script block');
}
const script = template.slice(scriptOpen + '<script>'.length, scriptClose);
const styleOpen = template.indexOf('<style>');
const styleClose = template.indexOf('</style>');
if (styleOpen < 0 || styleClose < 0) {
  throw new Error('card_board_script.html has no style block');
}
const style = template.slice(styleOpen, styleClose + '</style>'.length);

function slot(number, playerId) {
  const card = playerId
    ? `<article class="decision-card" data-player="${playerId}" data-kind="h">Hitter ${playerId}</article>`
    : '';
  return `<div class="lineup-slot">
    <div data-slot-number>${number}</div>
    <div class="slot-frame"><div class="slot-body slot-well">${card}</div></div>
    <input type="hidden" class="player-id" name="pinch_vs_rhp" value="${playerId || ''}">
  </div>`;
}

function hookButton(value, label, selected) {
  const on = selected ? ' bg-gray-800 text-white' : '';
  return `<button type="button" data-hook="${value}" class="border border-gray-400 px-1 leading-none${on}">${label}</button>`;
}

function rotationSlot(index, playerId, hook) {
  const card = playerId
    ? `<article class="decision-card" data-player="${playerId}" data-kind="p">Pitcher ${playerId}</article>`
    : '';
  const hidden = playerId ? '' : ' hidden';
  const buttons = [
    hookButton('', 'Default', hook === ''),
    hookButton('quick', 'Quick', hook === 'quick'),
    hookButton('normal', 'Normal', hook === 'normal'),
    hookButton('slow', 'Slow', hook === 'slow'),
  ].join('');
  return `<div class="rotation-slot lineup-slot" data-index="${index}">
    <div class="slot-body slot-well">${card}</div>
    <input type="hidden" class="player-id" name="rotation" value="${playerId || ''}">
    <div class="mt-1${hidden}" data-starter-hook>
      ${buttons}
      <input type="hidden" class="hook-value" name="hook_${index}" value="${hook}">
    </div>
  </div>`;
}

const html = `<!DOCTYPE html>
<html><head>${style}</head><body>
<div data-stack>
  <article class="decision-card" data-player="11" data-kind="h">Hitter 11</article>
  <article class="decision-card" data-player="7" data-kind="p">Pitcher 7</article>
</div>
<div data-lineup="pinch_vs_rhp">
  <div class="space-y-2">
    ${slot(1, '')}
    ${slot(2, '')}
    ${slot(3, '11')}
  </div>
  <button type="button" data-add-slot>Add a slot</button>
</div>
<div data-rotation>
  ${rotationSlot(1, '7', 'quick')}
  ${rotationSlot(2, '', '')}
</div>
<div class="lineup-column" data-lineup="vs_rhp">
  <div class="lineup-slot" data-spot="1">
    <div class="slot-frame"><div class="slot-body slot-well"><article class="decision-card" data-player="11" data-kind="h">Hitter 11</article></div>
    <button type="button" data-reorder draggable="true">Reorder</button></div>
    <div data-position-buttons><div data-position-main><button type="button" data-position="CF" class="bg-gray-800">CF</button></div>
    <input type="hidden" class="position-value" name="vs_rhp_position_1" value="CF"></div>
    <input type="hidden" class="player-id" name="vs_rhp_player_1" value="11">
  </div>
  <div class="lineup-slot" data-spot="2">
    <div class="slot-frame"><div class="slot-body slot-well"><article class="decision-card" data-player="21" data-kind="h">Hitter 21</article></div>
    <button type="button" data-reorder draggable="true">Reorder</button></div>
    <div data-position-buttons><div data-position-main><button type="button" data-position="SS" class="bg-gray-800">SS</button></div>
    <input type="hidden" class="position-value" name="vs_rhp_position_2" value="SS"></div>
    <input type="hidden" class="player-id" name="vs_rhp_player_2" value="21">
  </div>
  <div class="lineup-slot" data-spot="3">
    <div class="slot-frame"><div class="slot-body slot-well"></div></div>
    <input type="hidden" class="player-id" name="vs_rhp_player_3" value="">
  </div>
</div>
<script>${script}</script>
</body></html>`;

function check(failures, ok, message) {
  if (!ok) failures.push(message);
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

  const pinch = page.locator('[data-lineup="pinch_vs_rhp"]');
  await pinch.locator('[data-add-slot]').click();
  const slots = pinch.locator('.lineup-slot');
  const addedCount = await slots.count();
  check(failures, addedCount === 4, `add made ${addedCount} pinch slots`);
  if (addedCount !== 4) {
    await browser.close();
    console.error(failures.join('\n'));
    process.exit(1);
  }
  const added = slots.nth(3);
  check(failures, (await added.locator('[data-slot-number]').textContent()) === '4', 'new slot is numbered 4');
  check(failures, (await added.locator('.player-id').inputValue()) === '', 'new slot is empty');
  check(failures, (await added.locator('.decision-card').count()) === 0, 'new slot copied a card');
  check(failures, (await added.locator('.player-id').getAttribute('name')) === 'pinch_vs_rhp', 'new slot posts with the list');
  check(failures, (await slots.nth(2).locator('.player-id').inputValue()) === '11', 'adding a slot cleared the one it copied');

  await page.locator('[data-stack] [data-player="11"]').click();
  await added.locator('.slot-body').click();
  check(failures, (await added.locator('.player-id').inputValue()) === '11', 'the new slot accepts a hitter');
  check(failures, (await slots.nth(2).locator('.player-id').inputValue()) === '', 'the list keeps each hitter once');

  await pinch.locator('[data-add-slot]').click();
  check(failures, (await slots.count()) === 5, `second add made ${await slots.count()} pinch slots`);
  check(failures, (await slots.nth(4).locator('[data-slot-number]').textContent()) === '5', 'the next slot is numbered 5');

  const first = page.locator('[data-index="1"]');
  const second = page.locator('[data-index="2"]');
  await first.locator('button[data-hook="slow"]').click();
  check(failures, (await first.locator('.hook-value').inputValue()) === 'slow', 'Slow writes the hook field');
  check(failures, await first.locator('button[data-hook="slow"]').evaluate((el) => el.classList.contains('bg-gray-800') && el.classList.contains('text-white')), 'Slow is the selected button');
  check(failures, await first.locator('button[data-hook="quick"]').evaluate((el) => !el.classList.contains('bg-gray-800')), 'Quick is no longer selected');

  await first.locator('button[data-hook=""]').click();
  check(failures, (await first.locator('.hook-value').inputValue()) === '', 'Default clears the hook field');
  check(failures, await first.locator('button[data-hook=""]').evaluate((el) => el.classList.contains('bg-gray-800')), 'Default is the selected button');

  await first.locator('button[data-hook="slow"]').click();
  await page.locator('[data-stack] [data-player="7"]').click();
  await second.locator('.slot-body').click();
  check(failures, (await second.locator('.player-id').inputValue()) === '7', 'the pitcher moved to the next slot');
  check(failures, (await second.locator('.hook-value').inputValue()) === 'slow', 'his hook moved with him');
  check(failures, await second.locator('button[data-hook="slow"]').evaluate((el) => el.classList.contains('bg-gray-800')), 'the new slot shows Slow');
  check(failures, await second.locator('[data-starter-hook]').evaluate((el) => !el.classList.contains('hidden')), 'the hook row shows once a pitcher is there');
  check(failures, (await first.locator('.player-id').inputValue()) === '', 'the old slot is empty');
  check(failures, (await first.locator('.hook-value').inputValue()) === '', 'the old slot returns to Default');
  check(failures, await first.locator('[data-starter-hook]').evaluate((el) => el.classList.contains('hidden')), 'an empty slot hides its hook row');

  const order = page.locator('.lineup-column');
  const lead = order.locator('[data-spot="1"]');
  const next = order.locator('[data-spot="2"]');
  const open = order.locator('[data-spot="3"]');
  const hint = await open.locator('.slot-well').evaluate((el) => getComputedStyle(el, '::after').content);
  check(failures, hint.includes('Drop a hitter here'), `empty well names the drop: ${hint}`);
  await open.locator('.slot-well').dispatchEvent('dragover');
  check(failures, await open.evaluate((el) => el.classList.contains('is-over')), 'the empty well outlines while a card is over it');

  await lead.locator('[data-reorder]').click();
  await next.locator('[data-reorder]').click();
  check(failures, (await lead.locator('.player-id').inputValue()) === '21', 'the second hitter moved into the first spot');
  check(failures, (await next.locator('.player-id').inputValue()) === '11', 'the first hitter moved into the second spot');
  check(failures, (await lead.locator('.position-value').inputValue()) === 'SS', 'his position moved with him');
  check(failures, (await next.locator('.position-value').inputValue()) === 'CF', 'the other position stayed with its hitter');
  check(failures, (await lead.locator('.position-value').getAttribute('name')) === 'vs_rhp_position_1', 'the first spot still posts as the first spot');
  check(failures, (await lead.locator('.decision-card').count()) === 1, 'the first spot still holds one hitter');
  check(failures, (await next.locator('.decision-card').count()) === 1, 'the second spot still holds one hitter');

  await browser.close();
  if (failures.length) {
    console.error(failures.join('\n'));
    process.exit(1);
  }
  console.log('ok  a list grows by a slot, a hook moves with its pitcher, and a lineup swaps when it is reordered');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
