// ABOUTME: Node checks for the SNES field composer: integer scale, kit sprites, no anti-aliased primitives.
// ABOUTME: Imports the same pixelkit.mjs and game_field.js the game page loads.

import { composeField, integerScale, kitTeam, tagSide } from '../../ulmg/static/ulmg/game_field.js';
import { POS, project, VIEW, SPRITES, outlined } from '../../ulmg/static/ulmg/pixelkit.mjs';

function assert(cond, message) {
  if (!cond) throw new Error(message);
}

const state = {
  fielders: [
    { position: 'LF', name: 'Soto', short_name: 'Soto', rating: -5.5, fielding: '-5.5', skin: 'medium', team: 'home', x: POS.LF[0], z: POS.LF[1], sprite: 'fielder_ready', player_id: 1 },
    { position: 'CF', name: 'Lukes', short_name: 'Lukes', rating: 5.2, fielding: '+5.2', skin: 'light', team: 'home', x: POS.CF[0], z: POS.CF[1], sprite: 'fielder_ready', player_id: 2 },
    { position: 'RF', name: 'Tatis Jr', short_name: 'Tatis Jr', rating: 2.5, fielding: '+2.5', skin: 'medium', team: 'home', x: POS.RF[0], z: POS.RF[1], sprite: 'fielder_ready', player_id: 3 },
    { position: 'SS', name: 'Bogaerts', short_name: 'Bogaerts', rating: 2.7, fielding: '+2.7', skin: 'medium', team: 'home', x: POS.SS[0], z: POS.SS[1], sprite: 'fielder_ready', player_id: 4 },
    { position: '2B', name: 'Grissom', short_name: 'Grissom', rating: -9.8, fielding: '-9.8', skin: 'dark', team: 'home', x: POS['2B'][0], z: POS['2B'][1], sprite: 'fielder_ready', player_id: 5 },
    { position: '3B', name: 'Durbin', short_name: 'Durbin', rating: 4.1, fielding: '+4.1', skin: 'light', team: 'home', x: POS['3B'][0], z: POS['3B'][1], sprite: 'fielder_ready', player_id: 6 },
    { position: '1B', name: 'Johnston', short_name: 'Johnston', rating: -3.3, fielding: '-3.3', skin: 'light', team: 'home', x: POS['1B'][0], z: POS['1B'][1], sprite: 'fielder_ready', player_id: 7 },
    { position: 'C', name: 'Moreno', short_name: 'Moreno', rating: 7.9, fielding: '+7.9', skin: 'medium', team: 'home', x: POS.C[0], z: POS.C[1], sprite: 'catcher', player_id: 8 },
  ],
  pitcher: {
    name: 'Burke', short_name: 'Burke', throws: 'R', xfip_label: '4.00', pitches: 0, ceiling: 100,
    skin: 'light', team: 'home', x: POS.P[0], z: POS.P[1], sprite: 'pitch_set', player_id: 9,
  },
  batter: {
    name: 'Carroll', short_name: 'Carroll', hand: 'L', box: 'right', flip: true, slash: '.271 .340 .502',
    skin: 'medium', team: 'away', sprite: 'bat_stance', player_id: 10,
  },
  runners: [],
  banner: null,
  bases: { first: false, second: false, third: false },
};

const svg = composeField(state, 4);

assert(svg.includes('viewBox="0 0 320 180"'), 'logical field is 320×180');
assert(svg.includes('width="1280"') && svg.includes('height="720"'), '4× scale is 1280×720');
assert(svg.includes('shape-rendering="crispEdges"'), 'crispEdges on the root');

const uses = [...svg.matchAll(/<use href="#([^"]+)"[^>]*width="(\d+)" height="(\d+)"/g)];
assert(uses.length >= 8, 'every sprite declares its own width and height');
for (const [, id, w, h] of uses) {
  assert(
    svg.includes(`<symbol id="${id}" viewBox="0 0 ${w} ${h}"`),
    `${id} is drawn at its own ${w}×${h}, not stretched to the scaled viewport`,
  );
}
const batter = svg.match(/<use href="#sp-bat_stance[^"]+"[^>]*width="(\d+)"/);
assert(batter && Number(batter[1]) < 40, 'the batter stays sprite-sized inside the 320-wide field');
assert(!/<circle|<path |font-family|<ellipse/i.test(svg), 'no anti-aliased primitives or fonts');
assert(svg.includes('id="t-grassA"'), 'field plate uses the kit tiles');

const custom = composeField({
  ...state,
  park: { sprites: { plate_svg: '<g id="coors-plate"></g>' } },
}, 4);
assert(custom.includes('id="coors-plate"'), 'a stored plate replaces the generated field');
assert(!custom.includes('id="t-grassA"'), 'the generated grass is not drawn under a stored plate');
assert(custom.includes('data-sprite="fielder_ready"'), 'players still stand on a stored plate');
assert(svg.includes('data-sprite="fielder_ready"'), 'fielders use the ready sprite');
assert(svg.includes('data-sprite="catcher"'), 'the catcher uses the catcher sprite');
assert(svg.includes('data-sprite="pitch_set"'), 'the pitcher is in the set');
assert(svg.includes('data-sprite="bat_stance"'), 'the batter is in the stance');
assert(svg.includes('data-sprite="umpire"'), 'the umpire is on the field');
assert(svg.includes('href="#sp-bat_stance-ATL-medium-f"') || svg.includes("href='#sp-bat_stance-ATL-medium-f'"), 'LHB batter is the flipped ATL sprite');

const [cx] = project(...POS.CF);
assert(Math.abs(cx - VIEW.cx) < 1, `CF projects to centre, got ${cx}`);
assert(tagSide(Math.round(project(...POS.SS)[0])) === 'left', 'SS tag sits to the left');
assert(tagSide(Math.round(project(...POS['1B'])[0])) === 'right', '1B tag sits to the right');
assert(tagSide(Math.round(project(...POS.CF)[0])) === 'under', 'CF tag sits under the feet');

assert(integerScale(2000) === 5, 'a wide, tall window gets 5× (900px)');
assert(integerScale(1400) === 4, 'a 1400px-wide window gets 4× (720px)');
assert(integerScale(1100) === 3, 'a normal laptop gets 3× (540px), the crisp height nearest 600');
assert(integerScale(800) === 3, 'a narrow window holds 3× rather than a fractional scale');
assert(integerScale(2000, 700) === 3, 'a short laptop keeps the field at 540px instead of 720');
assert(integerScale(2000, 800) === 4, '800px of vertical room fits 4× and not 5×');
assert(integerScale(2000, 1100) === 5, 'a tall window still reaches 5×');
assert(integerScale(1000, 1100) === 3, 'width still caps the scale when the window is tall');
assert(kitTeam('home') === 'CHI' && kitTeam('away') === 'ATL', 'home whites, road grays');

const ready = outlined(SPRITES.fielder_ready);
assert(ready[0].length === 16 && ready.length === 24, 'ready sprite is 16×24 with the outline');

const pitched = composeField({
  ...state,
  banner: { outcome: 'single', kind: 'line', label: 'SINGLE', x: 80, z: 170, height_ft: 18 },
}, 4);
assert(pitched.includes('data-sprite="ball"'), 'a batted ball draws the ball sprite');

console.log('ok');
