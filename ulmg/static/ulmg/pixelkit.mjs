// ABOUTME: SNES-era pixel kit: palettes, sprite grids, bitmap fonts, field projection and rasterizer.
// ABOUTME: Source of truth for the live game field; imported by game_field.js. Do not reimplement in Python.
// pixelkit.mjs — 16-bit style pixel-art kit for the baseball sim.
// Everything renders to SVG <rect>s on an integer logical grid, then the root
// <svg> is scaled by an integer factor with shape-rendering="crispEdges".
// No raster images, no fonts to load, palette swaps are pure data.

// ───────────────────────────── PALETTES ─────────────────────────────
export const OUTLINE = '#1b1530';

export const TEAMS = {
  // W/w = uniform base/shadow, T/t = primary (cap, sleeves, belt, socks), A = accent (lettering)
  CHI: { name: 'CHI', W: '#f4f1e8', w: '#c4bfd3', T: '#2347a6', t: '#16306e', A: '#d23a30' }, // home whites
  ATL: { name: 'ATL', W: '#b8b9c6', w: '#878aa0', T: '#1d2b5e', t: '#111a3c', A: '#c8333b' }, // road grays
};

export const SKINS = {
  light:  { S: '#f2c29b', s: '#cf916a' },
  medium: { S: '#c68a5c', s: '#9c6340' },
  dark:   { S: '#8b5a3a', s: '#5f3b25' },
};

// Fixed (non-team) sprite colors
export const FIXED = {
  o: OUTLINE,
  G: '#b36a2b', g: '#7f4519',   // glove
  B: '#e0a861', b: '#a8743a',   // bat
  K: '#1f1b2e', k: '#4a4560',   // shoes / umpire cap
  X: '#ffffff',                 // ball, helmet shine
  U: '#2c3352', u: '#4a5480',   // catcher/umpire gear, ump shirt
  P: '#8d909e', p: '#666978',   // umpire slacks
  M: '#9aa0b5',                 // mask bars
};

export const FIELD = {
  grassA: '#3c9a3f', grassAspk: '#4fae4b',
  grassB: '#2f8536', grassBspk: '#287530',
  dirt: '#c27845', dirtSpk: '#d18a55', dirtSpk2: '#a9643a',
  dirtEdge: '#8f4f2e',
  track: '#a5623b', trackSpk: '#8f5432',
  chalk: '#f3efe2',
  wall: '#1d5c45', wallSeam: '#164a37', wallTop: '#f2c94c', wallShadow: '#226b32',
  crowd: '#2b2440', seat: '#3b3358',
  facade: '#232a4d', facadeHi: '#3a4680', light: '#fff3b0',
  shadow: 'rgba(10,8,25,0.38)',
};

export const HUD = {
  bg: '#141a3a', bg2: '#1d2552', borderHi: '#e9e4d4', borderLo: '#5a6aa8',
  text: '#f3efe2', dim: '#9aa3cc', orange: '#f59a23', orangeLo: '#b5650c',
  plus: '#7ee07e', minus: '#ff7a6b', textShadow: '#0b0d1e',
};

// ───────────────────────────── SPRITES ─────────────────────────────
// Grids are FILL ONLY. A 1px outline is added automatically around the
// silhouette (4-neighbour), so the output is +2px wide/tall.
// Keys: T t primary | W w uniform | A accent | S s skin | G g glove | B b bat
//       K k shoes | X white | U u gear | P p slacks | M mask | o interior line
// Anchor = bottom-centre of the output grid (feet). Shadows are drawn separately.

export const SPRITES = {
  // ── Fielder, front view, ready crouch (16×24) ──
  fielder_ready: [
    '.....TTTT.....',
    '....TTTXTT....',
    '....TTTTTT....',
    '..tttttttttt..',
    '....SSSSSS....',
    '....SoSSoS....',
    '....sSSSSs....',
    '.....sSSs.....',
    '...WWWssWWW...',
    '..TWWWWWWWWT..',
    '..TWWAAAAWWT..',
    '..SwWWWWWWwS..',
    '..SwWWWWWWwS..',
    '..SoTTTTTToS..',
    '..GGwWWWWwSS..',
    '.GGGgWWWWwSS..',
    '.GGgwWWwWWw...',
    '..WWWWw.wWWW..',
    '..WWWw...wWWW.',
    '.TTTt.....tTT.',
    '.TTTt.....tTT.',
    'KKKk......kKKK',
  ],
  // ── Fielder, glove up (catching) (16×24) ──
  fielder_catch: [
    '..........GGG.',
    '.....TTTTGGGGg',
    '....TTTXTGGGg.',
    '....TTTTTTSg..',
    '..ttttttttS...',
    '....SSSSSSS...',
    '....SoSSoSW...',
    '....sSSSSsW...',
    '.....sSSsWW...',
    '...WWWssWWW...',
    '..TWWWWWWWWT..',
    '..TWWAAAAWWT..',
    '..SwWWWWWWw...',
    '..SwWWWWWWw...',
    '..SSTTTTTT....',
    '...WWWWWWWW...',
    '...WWWwwWWW...',
    '...WWW..WWW...',
    '...WWw..wWW...',
    '...TTt..tTT...',
    '...TTt..tTT...',
    '..KKKk..kKKK..',
  ],
  // ── Runner, side view facing right, 2-frame cycle (16×24). Mirror for left. ──
  run_a: [
    '.....TTTT.....',
    '....TTTXTT....',
    '....TTTTTTtt..',
    '....tTTTSSs...',
    '....tTSSSoS...',
    '.....SSSSSS...',
    '.....sSSSs....',
    '......sS......',
    '.....WWWWT....',
    '....WWWWWTT...',
    '...SWWWWWWTS..',
    '..SSwWAAWw.SS.',
    '..S.wWWWWw....',
    '....TTTTTT....',
    '....WWWWWWW...',
    '...WWWw.WWWW..',
    '..WWWw...wWW..',
    '.WWw......TT..',
    'TTt.......TT..',
    'TT........TTt.',
    'KK........KKKk',
    'K.............',
  ],
  run_b: [
    '..............',
    '.....TTTT.....',
    '....TTTXTT....',
    '....TTTTTTtt..',
    '....tTTTSSs...',
    '....tTSSSoS...',
    '.....SSSSSS...',
    '.....sSSSs....',
    '......sS......',
    '.....WWWWT....',
    '....WWWWWTT...',
    '....WWWWWWS...',
    '....wWAAWwSS..',
    '....wWWWWw....',
    '....TTTTTT....',
    '....WWWWWW....',
    '....WWWwWW....',
    '.....WWwWWW...',
    '.....TTt.WW...',
    '.....TT..TT...',
    '.....TT..KKKk.',
    '....KKKk......',
  ],
  // ── Pitcher, front view (facing the plate / camera) 16×24, 3 frames ──
  pitch_set: [
    '.....TTTT.....',
    '....TTTXTT....',
    '....TTTTTT....',
    '..tttttttttt..',
    '....SSSSSS....',
    '....SoSSoS....',
    '....sSSSSs....',
    '.....sSSs.....',
    '...WWWssWWW...',
    '..TWWWWWWWWT..',
    '..TWWAAAAWWT..',
    '..wWWGGGSSWw..',
    '..WWWGGgSSWW..',
    '...wTTTTTTw...',
    '...WWWWWWWW...',
    '...WWWwwWWW...',
    '...WWW..WWW...',
    '...WWw..wWW...',
    '...TTt..tTT...',
    '...TTt..tTT...',
    '...TTt..tTT...',
    '..KKKk..kKKK..',
  ],
  pitch_kick: [
    '.....TTTT.....',
    '....TTTXTT....',
    '....TTTTTT....',
    '..tttttttttt..',
    '....SSSSSS....',
    '....SoSSoS....',
    '....sSSSSs....',
    '.....sSSs.....',
    '...WWWssWWW...',
    '..TWWWWWWWWT..',
    '..TWWAAAAWWT..',
    '..wWWGGGSSWw..',
    '..WWWGGgSSWW..',
    '...wTTTTTTWWW.',
    '...WWWWWWWWWWW',
    '...WWWwwWWwwWW',
    '...WWW...wTTT.',
    '...WWw....TTt.',
    '...TTt....KKk.',
    '...TTt........',
    '...TTt........',
    '..KKKk........',
  ],
  pitch_release: [
    'XS............',
    'SSs..TTTT.....',
    'sTs.TTTXTT....',
    '.TT.TTTTTT....',
    '.TTtttttttt...',
    '..TWSSSSSS....',
    '..TWSoSSoS....',
    '...WsSSSSs....',
    '...WWsSSsW....',
    '...WWWssWWW...',
    '...WWWWWWWWTT.',
    '...WWAAAAWWGG.',
    '...wWWWWWWwGGg',
    '...wTTTTTTw...',
    '..WWWWWWWWWW..',
    '.WWWw....wWWW.',
    '.WWw......wWW.',
    'WWw........WW.',
    'TTt........TT.',
    'TTt........TT.',
    'TT.........TTt',
    'KKk........KKK',
  ],
  // ── Batter, RHB, back view (camera behind the plate) 32×32, 3 frames. Mirror for LHB. ──
  bat_stance: [
    '..BB..........................',
    '..BBb.........................',
    '...BBb........................',
    '....BBb.......................',
    '.....BBb......................',
    '......BBb.TTTT................',
    '.......BBTTTTTTT..............',
    '........BTTXXTTTT.............',
    '.......SSTTXTTTTTT............',
    '.......SSTTTTTTTTt............',
    '.......SStTTTTTTts............',
    '........WWtTTTtsS.............',
    '.......WWWWWsssWWW............',
    '......WWWWWWWWWWWWW...........',
    '.....TWWWWWWWWWWWWWT..........',
    '.....TWWWAAWWWAAWWWT..........',
    '.....TwWWWWAWWWWAWWT..........',
    '......wWWWAWWWWAWWw...........',
    '......wWWAAAWWAAAWw...........',
    '......TTTTTTTTTTTTT...........',
    '......WWWWWWWWWWWWW...........',
    '.....WWWWWWwwWWWWWWW..........',
    '.....WWWWWw..wWWWWWW..........',
    '....WWWWw.....wWWWWW..........',
    '....WWWw.......wWWW...........',
    '....TTTt.......tTTT...........',
    '....TTTt.......tTTT...........',
    '....TTT.........TTT...........',
    '...KKKKk.......kKKKK..........',
    '...KKKK.........KKKK..........',
  ],
  bat_swing: [
    '..............................',
    '..............................',
    '..............................',
    '..............................',
    '..............................',
    '.........TTTT.................',
    '.......TTTTTTTT...............',
    '......TTXXTTTTTT..............',
    '......TTXTTTTTTTs.............',
    '......tTTTTTTTTSS.............',
    '.......sTTTTTtsSS.............',
    '.......WWsssWWWSSBBBBBBBBBBBBb',
    '......WWWWWWWWWWSSbbbbbbbbbbb.',
    '.....TWWWWWWWWWWWT............',
    '.....TWWWAAWWWAAWWT...........',
    '.....TwWWWWAWWWWAWW...........',
    '......wWWWAWWWWAWWw...........',
    '......wWWAAAWWAAAWw...........',
    '......TTTTTTTTTTTTT...........',
    '......WWWWWWWWWWWWW...........',
    '.....WWWWWWwwWWWWWWW..........',
    '.....WWWWWw..wWWWWWW..........',
    '....WWWWw.....wWWWWW..........',
    '....WWWw.......wWWW...........',
    '....TTTt.......tTTT...........',
    '....TTTt.......tTTT...........',
    '....TTT.........TTT...........',
    '...KKKKk.......KKKKk..........',
    '...KKKK.........KKKK..........',
    '..............................',
  ],
  bat_follow: [
    '..............................',
    '..............................',
    '..............................',
    '..............................',
    '..............................',
    '..........TTTT.....SS.........',
    '........TTTTTTTT..SSSb........',
    '.......TTXXTTTTTWSSBb.........',
    '.......TTXTTTTTTWWBb..........',
    '.......tTTTTTTTTWBb...........',
    '........sTTTTTtsBb............',
    '........WWsssWWBb.............',
    '.......WWWWWWWBbWW............',
    '......TWWWWWWBbWWWT...........',
    '......TWWAAWBbWAAWT...........',
    '......TwWWWABbWWAWT...........',
    '......wWWWBbWWWAWw............',
    '......wWWBbAWWAAAw............',
    '......TTBbTTTTTTTT............',
    '......WBbWWWWWWWWW............',
    '.....WBbWWWwwWWWWWW...........',
    '.....BbWWWw..wWWWWW...........',
    '....WWWWw.....wWWWWW..........',
    '....WWWw.......wWWW...........',
    '....TTTt.......tTTT...........',
    '....TTTt.......tTTT...........',
    '....TTT.........TTT...........',
    '...KKKKk.......kKKKK..........',
    '...KKKK.........KKKK..........',
    '..............................',
  ],
  // ── Catcher, back view, crouched (24×24) ──
  catcher: [
    '........TTTTTT........',
    '.......TTTTTTTT.......',
    '.......TTXTTTTt.......',
    '......MTTTTTTtM.......',
    '.......sTTTTts........',
    '......WWWWWWWWWW......',
    '....WWWWWWWWWWWWWW....',
    '...TWWWWAAWWAAWWWWT...',
    '...TWWWWWAWWWWAWWWT.GG',
    '...SwWWWWAWWWWAWWwSGGG',
    '...SwWWWAWWWWWAWWwSGGg',
    '....wWWWAAAWWAAAWw..g.',
    '....wWWWWWWWWWWWWw....',
    '....TTTTTTTTTTTTTT....',
    '...WWWWWWWWWWWWWWWW...',
    '..WWWWWWwwwwwwWWWWWW..',
    '.UUUWWWw......wWWWUUU.',
    '.UUuUww........wwUuUU.',
    '.UUUU............UUUU.',
    '.UUuU............UuUU.',
    'KKKKk............kKKKK',
    '.KKK..............KKK.',
  ],
  // ── Umpire, back view, leaning (24×28) ──
  umpire: [
    '.......KKKKKK.......',
    '......KKKKKKKK......',
    '......KKKKKKKk......',
    '......sKKKKKKs......',
    '.......sSSSSs.......',
    '....UUUUUUUUUUUU....',
    '...UUUUUUUUUUUUUU...',
    '..UUUUUUUUUUUUUUUU..',
    '..UUUuUUUUUUUUuUUU..',
    '..UUUuUUUUUUUUuUUU..',
    '..UUUuUUUUUUUUuUUU..',
    '..SUUUUUUUUUUUUUUS..',
    '..SSUUUUUUUUUUUUSS..',
    '...KKKKKKKKKKKKKK...',
    '...PPPPPPPPPPPPPP...',
    '...PPPPPPpPPPPPPP...',
    '...PPPPPp..pPPPPP...',
    '...PPPPp....pPPPP...',
    '...PPPP......PPPP...',
    '...PPPp......pPPP...',
    '...PPPp......pPPP...',
    '...PPPP......PPPP...',
    '...PPPp......pPPP...',
    '...PPPp......pPPP...',
    '..KKKKK......KKKKK..',
    '..KKKKk......kKKKK..',
  ],
  ball: ['.X.', 'XXX', '.X.'],
};

// Sprites whose last row should sit exactly on the anchor (feet).
export const SPRITE_INFO = {
  fielder_ready: { size: [16, 24] }, fielder_catch: { size: [16, 24] },
  run_a: { size: [16, 24] }, run_b: { size: [16, 24] },
  pitch_set: { size: [16, 24] }, pitch_kick: { size: [16, 24] }, pitch_release: { size: [16, 24] },
  bat_stance: { size: [32, 32] }, bat_swing: { size: [32, 32] }, bat_follow: { size: [32, 32] },
  catcher: { size: [24, 24] }, umpire: { size: [22, 28] }, ball: { size: [5, 5] },
};

// Expand grid by 1px and add the auto outline.
export function outlined(grid) {
  const w = Math.max(...grid.map(r => r.length));
  const g = grid.map(r => r.padEnd(w, '.'));
  const H = g.length + 2, W = w + 2;
  const out = Array.from({ length: H }, (_, y) =>
    Array.from({ length: W }, (_, x) => (y > 0 && y <= g.length && x > 0 && x <= w ? g[y - 1][x - 1] : '.')));
  const filled = (x, y) => y >= 0 && y < H && x >= 0 && x < W && out[y][x] !== '.' && out[y][x] !== '#';
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (out[y][x] !== '.') continue;
    if (filled(x - 1, y) || filled(x + 1, y) || filled(x, y - 1) || filled(x, y + 1)) out[y][x] = '#';
  }
  return out.map(r => r.map(c => (c === '#' ? 'o' : c)));
}

export function mirror(grid) { return grid.map(r => [...r].reverse()); }

export function paletteFor(team, skin = 'light') {
  return { ...FIXED, ...TEAMS[team], ...SKINS[skin] };
}

// Grid (2D array of keys) → rect list (horizontal runs).
function gridRects(grid, pal, ox = 0, oy = 0) {
  const parts = [];
  grid.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const c = row[x];
      if (c === '.') { x++; continue; }
      let e = x; while (e < row.length && row[e] === c) e++;
      parts.push(`<rect x="${ox + x}" y="${oy + y}" width="${e - x}" height="1" fill="${pal[c] ?? '#f0f'}"/>`);
      x = e;
    }
  });
  return parts.join('');
}

// Draw a sprite with its feet (bottom-centre) at (ax, ay). Returns SVG fragment.
export function sprite(name, { team = 'CHI', skin = 'light', flip = false, ax = 0, ay = 0, shadow = true } = {}) {
  let g = outlined(SPRITES[name]);
  if (flip) g = mirror(g);
  const w = g[0].length, h = g.length;
  const ox = Math.round(ax - w / 2), oy = ay - h + 1;
  let s = '';
  if (shadow) s += shadowAt(ax, ay, Math.max(8, Math.round(w * 0.7)));
  return s + `<g data-sprite="${name}">${gridRects(g, paletteFor(team, skin), ox, oy)}</g>`;
}

export function shadowAt(cx, cy, w = 12) {
  const x0 = Math.round(cx - w / 2);
  return `<g fill="${FIELD.shadow}"><rect x="${x0 + 2}" y="${cy}" width="${w - 4}" height="1"/>` +
    `<rect x="${x0}" y="${cy + 1}" width="${w}" height="1"/><rect x="${x0 + 2}" y="${cy + 2}" width="${w - 4}" height="1"/></g>`;
}

// Standalone sprite SVG (for the sheet / handoff), scaled.
export function spriteSVG(name, opts = {}, scale = 8) {
  let g = outlined(SPRITES[name]);
  if (opts.flip) g = mirror(g);
  const w = g[0].length, h = g.length;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w * scale}" height="${h * scale}" shape-rendering="crispEdges">${gridRects(g, paletteFor(opts.team ?? 'CHI', opts.skin ?? 'light'))}</svg>`;
}

// ───────────────────────────── FONTS ─────────────────────────────
// 5×7 "HUD" font and 3×5 "tag" font. Uppercase only.
const F5 = {
  A: '.###.|#...#|#...#|#####|#...#|#...#|#...#', B: '####.|#...#|#...#|####.|#...#|#...#|####.',
  C: '.###.|#...#|#....|#....|#....|#...#|.###.', D: '####.|#...#|#...#|#...#|#...#|#...#|####.',
  E: '#####|#....|#....|####.|#....|#....|#####', F: '#####|#....|#....|####.|#....|#....|#....',
  G: '.###.|#...#|#....|#.###|#...#|#...#|.####', H: '#...#|#...#|#...#|#####|#...#|#...#|#...#',
  I: '.###.|..#..|..#..|..#..|..#..|..#..|.###.', J: '..###|...#.|...#.|...#.|...#.|#..#.|.##..',
  K: '#...#|#..#.|#.#..|##...|#.#..|#..#.|#...#', L: '#....|#....|#....|#....|#....|#....|#####',
  M: '#...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#', N: '#...#|#...#|##..#|#.#.#|#..##|#...#|#...#',
  O: '.###.|#...#|#...#|#...#|#...#|#...#|.###.', P: '####.|#...#|#...#|####.|#....|#....|#....',
  Q: '.###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#', R: '####.|#...#|#...#|####.|#.#..|#..#.|#...#',
  S: '.####|#....|#....|.###.|....#|....#|####.', T: '#####|..#..|..#..|..#..|..#..|..#..|..#..',
  U: '#...#|#...#|#...#|#...#|#...#|#...#|.###.', V: '#...#|#...#|#...#|#...#|#...#|.#.#.|..#..',
  W: '#...#|#...#|#...#|#.#.#|#.#.#|#.#.#|.#.#.', X: '#...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#',
  Y: '#...#|#...#|.#.#.|..#..|..#..|..#..|..#..', Z: '#####|....#|...#.|..#..|.#...|#....|#####',
  0: '.###.|#...#|#..##|#.#.#|##..#|#...#|.###.', 1: '..#..|.##..|..#..|..#..|..#..|..#..|.###.',
  2: '.###.|#...#|....#|...#.|..#..|.#...|#####', 3: '####.|....#|....#|.###.|....#|....#|####.',
  4: '...#.|..##.|.#.#.|#..#.|#####|...#.|...#.', 5: '#####|#....|####.|....#|....#|#...#|.###.',
  6: '..##.|.#...|#....|####.|#...#|#...#|.###.', 7: '#####|....#|...#.|..#..|.#...|.#...|.#...',
  8: '.###.|#...#|#...#|.###.|#...#|#...#|.###.', 9: '.###.|#...#|#...#|.####|....#|...#.|.##..',
  '.': '.....|.....|.....|.....|.....|.##..|.##..', '-': '.....|.....|.....|.###.|.....|.....|.....',
  '+': '.....|..#..|..#..|#####|..#..|..#..|.....', ':': '.....|.##..|.##..|.....|.##..|.##..|.....',
  '/': '....#|....#|...#.|..#..|.#...|#....|#....', "'": '..#..|..#..|.#...|.....|.....|.....|.....',
  '&': '.##..|#..#.|#.#..|.#...|#.#.#|#..#.|.##.#', '>': '#....|.#...|..#..|...#.|..#..|.#...|#....',
  '·': '.....|.....|.....|..#..|.....|.....|.....', ' ': '.....|.....|.....|.....|.....|.....|.....',
};
const F3 = {
  A: '.#.|#.#|###|#.#|#.#', B: '##.|#.#|##.|#.#|##.', C: '.##|#..|#..|#..|.##', D: '##.|#.#|#.#|#.#|##.',
  E: '###|#..|##.|#..|###', F: '###|#..|##.|#..|#..', G: '.##|#..|#.#|#.#|.##', H: '#.#|#.#|###|#.#|#.#',
  I: '###|.#.|.#.|.#.|###', J: '..#|..#|..#|#.#|.#.', K: '#.#|#.#|##.|#.#|#.#', L: '#..|#..|#..|#..|###',
  M: '#.#|###|###|#.#|#.#', N: '##.|#.#|#.#|#.#|#.#', O: '.#.|#.#|#.#|#.#|.#.', P: '##.|#.#|##.|#..|#..',
  Q: '.#.|#.#|#.#|##.|.##', R: '##.|#.#|##.|#.#|#.#', S: '.##|#..|.#.|..#|##.', T: '###|.#.|.#.|.#.|.#.',
  U: '#.#|#.#|#.#|#.#|###', V: '#.#|#.#|#.#|#.#|.#.', W: '#.#|#.#|###|###|#.#', X: '#.#|#.#|.#.|#.#|#.#',
  Y: '#.#|#.#|.#.|.#.|.#.', Z: '###|..#|.#.|#..|###',
  0: '###|#.#|#.#|#.#|###', 1: '.#.|##.|.#.|.#.|###', 2: '##.|..#|.#.|#..|###', 3: '##.|..#|.#.|..#|##.',
  4: '#.#|#.#|###|..#|..#', 5: '###|#..|##.|..#|##.', 6: '.##|#..|###|#.#|###', 7: '###|..#|.#.|.#.|.#.',
  8: '###|#.#|###|#.#|###', 9: '###|#.#|###|..#|##.',
  '.': '...|...|...|...|.#.', '-': '...|...|###|...|...', '+': '...|.#.|###|.#.|...', '/': '..#|..#|.#.|#..|#..',
  ':': '...|.#.|...|.#.|...', ' ': '...|...|...|...|...',
};
export const FONTS = { hud: { glyphs: F5, w: 5, h: 7, adv: 6 }, tag: { glyphs: F3, w: 3, h: 5, adv: 4 } };

export function textWidth(str, font = 'hud') { return str.length * FONTS[font].adv - 1; }

// Text as pixel rects. align: 'left' | 'center' | 'right'. shadow: colour or null (drop 1px down-right).
export function text(str, x, y, { font = 'hud', color = HUD.text, shadow = HUD.textShadow, align = 'left', scale = 1 } = {}) {
  const f = FONTS[font];
  str = String(str).toUpperCase();
  const w = textWidth(str, font) * scale;
  if (align === 'center') x = Math.round(x - w / 2); else if (align === 'right') x = x - w;
  const pix = [];
  [...str].forEach((ch, i) => {
    const rows = (f.glyphs[ch] ?? f.glyphs[' ']).split('|');
    rows.forEach((r, ry) => { let cx = 0; while (cx < r.length) { if (r[cx] !== '#') { cx++; continue; } let e = cx; while (e < r.length && r[e] === '#') e++; pix.push([x + (i * f.adv + cx) * scale, y + ry * scale, (e - cx) * scale]); cx = e; } });
  });
  const draw = (dx, dy, c) => `<g fill="${c}">` + pix.map(([px, py, pw]) => `<rect x="${px + dx}" y="${py + dy}" width="${pw}" height="${scale}"/>`).join('') + '</g>';
  return (shadow ? draw(scale, scale, shadow) : '') + draw(0, 0, color);
}

// SNES-style window: dark fill, light outer border, inner bevel.
export function box(x, y, w, h, { fill = HUD.bg, hi = HUD.borderHi, lo = HUD.borderLo, accent = null } = {}) {
  const a = accent ?? hi;
  return `<g><rect x="${x + 1}" y="${y}" width="${w - 2}" height="${h}" fill="${OUTLINE}"/><rect x="${x}" y="${y + 1}" width="${w}" height="${h - 2}" fill="${OUTLINE}"/>` +
    `<rect x="${x + 1}" y="${y + 1}" width="${w - 2}" height="${h - 2}" fill="${a}"/>` +
    `<rect x="${x + 2}" y="${y + 2}" width="${w - 4}" height="${h - 4}" fill="${lo}"/>` +
    `<rect x="${x + 3}" y="${y + 3}" width="${w - 6}" height="${h - 6}" fill="${fill}"/></g>`;
}

// ───────────────────────────── FIELD ─────────────────────────────
// Camera sits high behind home plate. World: feet, origin at home plate,
// +z toward centre field, +x toward the 1B/right-field side.
export const VIEW = { W: 320, H: 180, cx: 160, hz: -72.4, K: 67968, Kx: 420, d: 320 };

export function project(x, z, v = VIEW) {
  const den = z + v.d;
  return [v.cx + (v.Kx * x) / den, v.hz + v.K / den];
}
export function unproject(sx, sy, v = VIEW) {
  const z = v.K / (sy - v.hz) - v.d;
  return [((sx - v.cx) * (z + v.d)) / v.Kx, z];
}
// scale factor (1 at home plate) — use for wall heights / optional sprite tiers
export const depthScale = (z, v = VIEW) => v.d / (z + v.d);

export const POS = {
  P: [0, 60.5], C: [0, -10], '1B': [52, 80], '2B': [36, 136], SS: [-36, 136], '3B': [-52, 80],
  LF: [-150, 255], CF: [0, 315], RF: [150, 255], UMP: [-10, -24],
  BAT_R: [-7, 0], BAT_L: [7, 0],
  base1: [63.6, 63.6], base2: [0, 127.3], base3: [-63.6, 63.6], home: [0, 0],
};

const fenceR = th => 330 + 70 * Math.cos(2 * Math.min(Math.abs(th), Math.PI / 4));
const SIDE_WALL = 52;  // ft of foul ground outside the lines

function classify(x, z) {
  const r = Math.hypot(x, z), th = Math.atan2(x, z);
  const outL = (-x - z) / Math.SQRT2, outR = (x - z) / Math.SQRT2; // >0 = foul side
  const side = Math.max(outL, outR);
  if (side > SIDE_WALL) return 'beyondS';
  if (r > fenceR(th)) return 'beyondF';
  if (r > fenceR(th) - 16 || side > SIDE_WALL - 10) return 'track';
  const u = (z + x) / Math.SQRT2, v = (z - x) / Math.SQRT2;
  const dm = Math.hypot(x, z - 60.5), dh = Math.hypot(x, z);
  if (dm <= 10) return 'dirt';
  if (dh <= 16) return 'dirt';
  const inGrass = u >= 5 && v >= 5 && u <= 85 && v <= 85;
  if (inGrass) return grassCheck(u, v);
  if (dm <= 95 && side < 8) return 'dirt';
  if (Math.abs(side) <= 4 && Math.max(u, v) <= 92 && Math.min(u, v) > -4) return 'dirt';
  return grassCheck(u, v);
}
function grassCheck(u, v) { return ((Math.floor(u / 30) + Math.floor(v / 30)) & 1) ? 'grassB' : 'grassA'; }

// 8×8 tiles (authentic SNES BG tiles) used as SVG pattern fills on run-length rects.
const TILES = {
  grassA: { w: 8, h: 8, base: FIELD.grassA, px: [[1, 1, FIELD.grassAspk], [5, 2, FIELD.grassAspk], [2, 5, FIELD.grassAspk], [6, 6, FIELD.grassAspk], [3, 3, FIELD.grassBspk]] },
  grassB: { w: 8, h: 8, base: FIELD.grassB, px: [[2, 1, FIELD.grassBspk], [6, 3, FIELD.grassBspk], [1, 6, FIELD.grassBspk], [5, 6, FIELD.grassAspk]] },
  dirt: { w: 8, h: 8, base: FIELD.dirt, px: [[1, 2, FIELD.dirtSpk], [5, 1, FIELD.dirtSpk2], [3, 6, FIELD.dirtSpk], [6, 5, FIELD.dirtSpk2]] },
  track: { w: 8, h: 8, base: FIELD.track, px: [[2, 2, FIELD.trackSpk], [6, 5, FIELD.trackSpk], [4, 0, FIELD.dirt]] },
  crowd: (() => {
    const heads = ['#d9a888', '#a8744e', '#7a4f34', '#c99a76', '#8c5c3c'];
    const shirts = ['#a83c4a', '#3d5fa8', '#b9b4c8', '#b8963c', '#2a3f86', '#4a8a52', '#8c3442', '#6c4a8c'];
    const px = [];
    for (let row = 0; row < 2; row++) for (let i = 0; i < 6; i++) {
      const x = i * 4 + (row ? 2 : 0), y = row * 5;
      px.push([x + 1, y + 1, heads[(i * 3 + row) % heads.length]]);
      px.push([x, y + 2, shirts[(i * 5 + row * 3) % shirts.length]], [x + 1, y + 2, shirts[(i * 5 + row * 3) % shirts.length]], [x + 2, y + 2, shirts[(i * 5 + row * 3) % shirts.length]]);
      px.push([x, y + 3, FIELD.seat], [x + 1, y + 3, FIELD.seat], [x + 2, y + 3, FIELD.seat], [x + 3, y + 3, FIELD.seat]);
    }
    return { w: 24, h: 10, base: FIELD.crowd, px };
  })(),
};

function patternDefs() {
  return '<defs>' + Object.entries(TILES).map(([k, t]) =>
    `<pattern id="t-${k}" patternUnits="userSpaceOnUse" width="${t.w}" height="${t.h}"><rect width="${t.w}" height="${t.h}" fill="${t.base}"/>` +
    t.px.map(([x, y, c]) => `<rect x="${x}" y="${y}" width="1" height="1" fill="${c}"/>`).join('') + '</pattern>').join('') + '</defs>';
}

const FILL = {
  grassA: 'url(#t-grassA)', grassB: 'url(#t-grassB)', dirt: 'url(#t-dirt)', track: 'url(#t-track)', crowd: 'url(#t-crowd)',
  edge: FIELD.dirtEdge, wall: FIELD.wall, seam: FIELD.wallSeam, wallTop: FIELD.wallTop, chalk: FIELD.chalk,
  facade: FIELD.facade, facadeHi: FIELD.facadeHi, light: FIELD.light, trackShade: FIELD.trackSpk,
};

// Build the static field as SVG (W×H logical px). Returns { svg, map } where map is the class grid.
export function buildField(v = VIEW) {
  const { W, H } = v;
  const m = Array.from({ length: H }, () => new Array(W));
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const [wx, wz] = unproject(x + 0.5, y + 0.5, v);
    m[y][x] = classify(wx, wz);
  }
  // Wall faces. Outfield fence: wall rises ABOVE its base (field below it).
  // Side walls along the lines: a short wall cap on the stands side, field above it.
  const isB = c => c === 'beyondF' || c === 'beyondS';
  const out = m.map(r => r.slice());
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const c = m[y][x]; if (!isB(c)) continue;
    const [, wz] = unproject(x + 0.5, y + 0.5, v);
    const h = Math.max(4, Math.round(14 * depthScale(Math.max(wz, 0), v)));
    let wall = false;
    if (c === 'beyondF') { for (let k = 1; k <= h; k++) if (y + k < H && !isB(m[y + k][x])) { wall = true; break; } }
    else { for (let k = 1; k <= 3; k++) if (y - k >= 0 && !isB(m[y - k][x])) { wall = true; break; } }
    out[y][x] = wall ? ((x % 12 === 0) ? 'seam' : 'wall') : 'crowd';
  }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (out[y][x] !== 'wall' && out[y][x] !== 'seam') continue;
    const up = y > 0 ? out[y - 1][x] : 'crowd';
    if (m[y][x] === 'beyondF' && up === 'crowd') out[y][x] = 'wallTop';
    if (m[y][x] === 'beyondS' && y > 0 && !isB(m[y - 1][x])) out[y][x] = 'wallTop';
  }
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    m[y][x] = out[y][x];
    if (m[y][x] === 'track' && y > 0 && ['wall', 'seam'].includes(out[y - 1][x])) m[y][x] = 'trackShade';
  }
  // Upper-deck facade across the top
  for (let y = 0; y < 7; y++) for (let x = 0; x < W; x++) if (m[y][x] === 'crowd')
    m[y][x] = y === 6 ? 'facadeHi' : (y >= 2 && y <= 3 && x % 16 >= 6 && x % 16 <= 9 ? 'light' : 'facade');
  // Dirt lip where dirt meets grass
  const isGrass = c => c === 'grassA' || c === 'grassB';
  const edges = [];
  for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++)
    if (m[y][x] === 'dirt' && (isGrass(m[y - 1][x]) || isGrass(m[y + 1][x]) || isGrass(m[y][x - 1]) || isGrass(m[y][x + 1]))) edges.push([x, y]);
  edges.forEach(([x, y]) => (m[y][x] = 'edge'));
  // Chalk: foul lines (home → wall), batter's boxes
  const chalkLine = (x0, z0, x1, z1) => {
    const steps = 800;
    for (let i = 0; i <= steps; i++) {
      const t = i / steps, [sx, sy] = project(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, v);
      const px = Math.floor(sx), py = Math.floor(sy);
      if (py >= 0 && py < H && px >= 0 && px < W && !['crowd', 'wall', 'seam', 'wallTop', 'facade', 'facadeHi', 'light'].includes(m[py][px])) m[py][px] = 'chalk';
    }
  };
  chalkLine(3, 3, 260, 260); chalkLine(-3, 3, -260, 260);
  // batter's boxes (exaggerated so they read at this scale)
  for (const s of [-1, 1]) {
    const x0 = s * 3, x1 = s * 10, z0 = -6, z1 = 6;
    chalkLine(x0, z0, x1, z0); chalkLine(x0, z1, x1, z1); chalkLine(x0, z0, x0, z1); chalkLine(x1, z0, x1, z1);
  }
  // catcher's box
  chalkLine(-4, -6, -4, -14); chalkLine(4, -6, 4, -14);

  // Run-length encode to rects
  const parts = [];
  for (let y = 0; y < H; y++) {
    let x = 0;
    while (x < W) { const c = m[y][x]; let e = x; while (e < W && m[y][e] === c) e++; parts.push(`<rect x="${x}" y="${y}" width="${e - x}" height="1" fill="${FILL[c]}"/>`); x = e; }
  }
  // Bases, plate, rubber (hand-placed pixel art on top)
  const bases = [];
  for (const k of ['base1', 'base2', 'base3']) { const [sx, sy] = project(...POS[k], v); bases.push(baseSprite(Math.round(sx), Math.round(sy))); }
  const [hx, hy] = project(0, 0, v);
  bases.push(plateSprite(Math.round(hx), Math.round(hy)));
  const [mx, my] = project(0, 60.5, v);
  bases.push(`<rect x="${Math.round(mx) - 3}" y="${Math.round(my) - 1}" width="6" height="1" fill="${FIELD.chalk}"/>`);
  // distance markers
  const marks = [[0, 'CF'], [-Math.PI / 4 + 0.03, 'L'], [Math.PI / 4 - 0.03, 'R']].map(([th, k]) => {
    const R = fenceR(th) + 1, [sx, sy] = project(R * Math.sin(th), R * Math.cos(th), v);
    const label = k === 'CF' ? '400' : '330';
    return text(label, Math.round(sx), Math.round(sy) - (k === 'CF' ? 6 : 8), { font: 'tag', color: FIELD.wallTop, shadow: null, align: 'center' });
  });
  return { svg: patternDefs() + `<g shape-rendering="crispEdges">${parts.join('')}${bases.join('')}${marks.join('')}</g>`, map: m, rects: parts.length };
}

function baseSprite(cx, cy) {
  // 7×4 white bag in perspective, outlined
  const g = ['..o.o..'.replace(/o/g, 'o'), '.oWWWo.', 'oWWWWWo', '.owwwo.'];
  const rows = ['..ooo..', '.oWWWo.', 'oWWWWWo', '.owwwo.', '..ooo..'];
  const pal = { o: OUTLINE, W: '#ffffff', w: '#c9c3d6' };
  return gridRects(rows.map(r => [...r]), pal, cx - 3, cy - 2);
}
function plateSprite(cx, cy) {
  const rows = ['ooooooooo', 'oWWWWWWWo', 'oWWWWWWWo', '.owWWWwo.', '..owwwo..', '...ooo...'];
  return gridRects(rows.map(r => [...r]), { o: OUTLINE, W: '#ffffff', w: '#c9c3d6' }, cx - 4, cy - 2);
}

export { gridRects };
