// ABOUTME: Composes the live SNES field from pixelkit.mjs and the JSON Django puts on the page.
// ABOUTME: Integer scale only. A stored field plate replaces the generic park; player sprites stay kit symbols.

import {
  SPRITES, outlined, mirror, paletteFor, gridRects, shadowAt, text, box, textWidth,
  buildField, project, POS, VIEW, HUD, OUTLINE,
} from './pixelkit.mjs';

const MIN_SCALE = 4;
const MAX_SCALE = 5;
const BAT_DX = 22;
let generatedPlate = null;
const symbolCache = new Map();

export function kitTeam(side) {
  return side === 'away' ? 'ATL' : 'CHI';
}

export function integerScale(cssWidth, logicalW = VIEW.W, minHeight = 720) {
  const minScale = Math.max(MIN_SCALE, Math.ceil(minHeight / VIEW.H));
  const fitted = Math.max(1, Math.floor((cssWidth || logicalW * minScale) / logicalW));
  return Math.min(MAX_SCALE, Math.max(minScale, fitted));
}

export function tagSide(ax) {
  if (ax < 148) return 'left';
  if (ax > 172) return 'right';
  return 'under';
}

function fieldPlate(state) {
  const stored = state && state.park && state.park.sprites && state.park.sprites.plate_svg;
  if (stored) return stored;
  if (!generatedPlate) generatedPlate = buildField();
  return generatedPlate.svg;
}

function spriteGrid(name, flip) {
  let grid = outlined(SPRITES[name]);
  if (flip) grid = mirror(grid);
  return grid;
}

function symbolId(name, team, skin, flip) {
  return `sp-${name}-${team}-${skin}${flip ? '-f' : ''}`;
}

function ensureSymbol(name, team, skin, flip = false) {
  const id = symbolId(name, team, skin, flip);
  if (symbolCache.has(id)) return symbolCache.get(id);
  const grid = spriteGrid(name, flip);
  const w = grid[0].length;
  const h = grid.length;
  const body = `<symbol id="${id}" viewBox="0 0 ${w} ${h}" overflow="visible">${gridRects(grid, paletteFor(team, skin))}</symbol>`;
  symbolCache.set(id, { id, w, h, body });
  return symbolCache.get(id);
}

function place(name, ax, ay, { team = 'CHI', skin = 'light', flip = false, shadow = true } = {}) {
  const usedTeam = (team === 'home' || team === 'away') ? kitTeam(team) : team;
  const sym = ensureSymbol(name, usedTeam, skin, flip);
  const ox = Math.round(ax - sym.w / 2);
  const oy = ay - sym.h + 1;
  const shade = shadow ? shadowAt(ax, ay, Math.max(8, Math.round(sym.w * 0.7))) : '';
  return {
    ay,
    shadow: shade,
    sprite: `<use href="#${sym.id}" x="${ox}" y="${oy}" data-sprite="${name}"/>`,
  };
}

function tag({ x, y, name, pos, rating }) {
  const r = Number(rating) || 0;
  const rt = `${r > 0 ? '+' : ''}${r.toFixed(1)}`;
  const rc = r >= 0 ? HUD.plus : HUD.minus;
  const l2 = textWidth(pos, 'tag') + 4 + textWidth(rt, 'tag');
  const w = Math.max(textWidth(name, 'tag'), l2);
  const side = tagSide(x);
  let lx;
  let ly;
  if (side === 'left') {
    lx = x - 11 - w;
    ly = y - 19;
  } else if (side === 'right') {
    lx = x + 11;
    ly = y - 19;
  } else {
    lx = Math.round(x - w / 2);
    ly = y + 4;
  }
  const alignR = side === 'left';
  const nx = alignR ? lx + w - textWidth(name, 'tag') : lx;
  const px = alignR ? lx + w - l2 : lx;
  return text(name, nx, ly, { font: 'tag' })
    + text(pos, px, ly + 6, { font: 'tag', color: HUD.dim })
    + text(rt, px + textWidth(pos, 'tag') + 4, ly + 6, { font: 'tag', color: rc });
}

function atWorld(x, z) {
  const [sx, sy] = project(x, z);
  return [Math.round(sx), Math.round(sy)];
}

function fatigueFill(pitches, limit) {
  if (!limit) return { width: 0, color: HUD.plus };
  const share = pitches / limit;
  const width = Math.max(0, Math.min(72, Math.round(72 * share)));
  const color = share > 0.9 ? HUD.minus : share > 0.7 ? HUD.orange : HUD.plus;
  return { width, color };
}

function cards(state) {
  let svg = '';
  const batter = state.batter;
  if (batter) {
    svg += box(3, 150, 78, 27);
    svg += text(batter.short_name || batter.name || '', 8, 155);
    svg += text(`${batter.hand || '?'}HB`, 76, 155, { font: 'tag', color: HUD.orange, align: 'right' });
    svg += text(batter.slash || '—', 8, 165, { font: 'tag', color: HUD.dim });
  }
  const pitcher = state.pitcher;
  if (pitcher) {
    const px0 = 233;
    const py0 = 150;
    const bar = fatigueFill(pitcher.pitches || 0, pitcher.ceiling || 0);
    const throws = pitcher.throws && pitcher.throws !== '?' ? `${pitcher.throws}HP` : '';
    svg += box(px0, py0, 84, 27, { accent: HUD.orange });
    svg += text(pitcher.short_name || pitcher.name || '', px0 + 5, py0 + 5, { color: HUD.orange });
    if (throws) svg += text(throws, px0 + 79, py0 + 5, { font: 'tag', color: HUD.dim, align: 'right' });
    svg += text(`XFIP ${pitcher.xfip_label || '—'}`, px0 + 5, py0 + 15, { font: 'tag' });
    svg += text(`${pitcher.pitches || 0} P`, px0 + 79, py0 + 15, { font: 'tag', align: 'right' });
    svg += `<rect x="${px0 + 5}" y="${py0 + 21}" width="74" height="3" fill="${OUTLINE}"/>`;
    svg += `<rect x="${px0 + 6}" y="${py0 + 21}" width="72" height="2" fill="#2a325e"/>`;
    if (bar.width) svg += `<rect x="${px0 + 6}" y="${py0 + 21}" width="${bar.width}" height="2" fill="${bar.color}"/>`;
  }
  return svg;
}

function actors(state) {
  const items = [];
  const labels = [];
  const [hx, hy] = atWorld(0, 0);

  for (const fielder of state.fielders || []) {
    if (fielder.position === 'C') continue;
    const [x, y] = atWorld(fielder.x, fielder.z);
    items.push(place(fielder.sprite || 'fielder_ready', x, y, { team: fielder.team, skin: fielder.skin }));
    labels.push({ x, y, name: fielder.short_name || fielder.name, pos: fielder.position, rating: fielder.rating });
  }

  if (state.pitcher) {
    const [x, y] = atWorld(state.pitcher.x, state.pitcher.z);
    items.push(place(state.pitcher.sprite || 'pitch_set', x, y - 2, { team: state.pitcher.team, skin: state.pitcher.skin }));
  }

  for (const runner of state.runners || []) {
    const [x, y] = atWorld(runner.x, runner.z);
    items.push(place(runner.sprite || 'run_a', x, y, { team: runner.team, skin: runner.skin, flip: runner.base !== 'first' }));
  }

  if (state.batter) {
    const flip = Boolean(state.batter.flip);
    const x = hx + (flip ? BAT_DX : -BAT_DX);
    const y = hy + 1;
    items.push(place(state.batter.sprite || 'bat_stance', x, y, { team: state.batter.team, skin: state.batter.skin, flip }));
  }

  const catcher = (state.fielders || []).find((f) => f.position === 'C');
  if (catcher) {
    const x = hx - 2;
    const y = hy + 8;
    items.push(place('catcher', x, y, { team: catcher.team, skin: catcher.skin }));
    labels.push({ x, y, name: catcher.short_name || catcher.name, pos: 'C', rating: catcher.rating });
  }

  const umpX = hx + (state.batter && state.batter.flip ? -20 : 20);
  items.push(place('umpire', umpX, Math.min(hy + 19, 179), { team: 'CHI', skin: 'light' }));

  let ball = '';
  if (state.banner && state.banner.z != null) {
    const [bx, by] = atWorld(state.banner.x, state.banner.z);
    const px = 420 / (state.banner.z + 320);
    const height = Math.round((state.banner.height_ft || 12) * px);
    ball = shadowAt(bx, by, 4) + place('ball', bx, by - height, { shadow: false }).sprite;
  }

  items.sort((a, b) => a.ay - b.ay);
  return items.map((i) => i.shadow).join('')
    + items.map((i) => i.sprite).join('')
    + ball
    + labels.map(tag).join('');
}

export function composeField(state, scale = MIN_SCALE) {
  symbolCache.clear();
  const layer = actors(state) + cards(state);
  const symbols = [...symbolCache.values()].map((s) => s.body).join('');
  const w = VIEW.W * scale;
  const h = VIEW.H * scale;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${VIEW.W} ${VIEW.H}" width="${w}" height="${h}" shape-rendering="crispEdges">`
    + `<defs>${symbols}</defs>`
    + fieldPlate(state)
    + layer
    + '</svg>';
}

function hostWidth(host) {
  const screen = host.closest('.game-screen');
  return (screen && screen.clientWidth) || host.clientWidth || window.innerWidth;
}

function paint(host, state) {
  host.innerHTML = composeField(state, integerScale(hostWidth(host)));
}

function boot() {
  if (typeof document === 'undefined') return;
  const data = document.getElementById('game-field-data');
  const host = document.getElementById('game-field');
  if (!data || !host) return;
  const state = JSON.parse(data.textContent);
  paint(host, state);
  window.addEventListener('resize', () => paint(host, state));
}

boot();
