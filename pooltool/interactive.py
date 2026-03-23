"""Interactive web-based pool table editor.

Serves the table image as a background with draggable ball sprites.
Export positions as CLI args when done.
"""

import io
import base64

from flask import Flask, render_template_string, jsonify

from pooltool.table import TABLES
from pooltool.renderer import TableRenderer, BALL_COLORS

app = Flask(__name__)

# Default config
TABLE_SIZE = "9foot"
PPI = 24.0


def get_renderer():
    config = TABLES[TABLE_SIZE]
    return TableRenderer(config, pixels_per_inch=PPI)


def get_table_image_data():
    """Render an empty table and return as base64 PNG."""
    renderer = get_renderer()
    img = renderer.render()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def render_ball_image(ball_number):
    """Render a single ball on transparent background and return as base64 PNG."""
    from PIL import Image, ImageDraw
    renderer = get_renderer()
    config = renderer.config
    r = config.ball_radius * renderer.ppi
    size = int(r * 2 + 4)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Temporarily shift renderer to draw ball at center of this small image
    orig_offset_x = renderer.offset_x
    orig_offset_y = renderer.offset_y
    renderer.offset_x = size / 2 - 0  # center of small image maps to table (0,0)
    renderer.offset_y = size / 2 - 0
    # Override table_to_pixel to center the ball
    cx, cy = size / 2, size / 2
    renderer.offset_x = cx - config.half_width * renderer.ppi
    renderer.offset_y = cy - config.half_length * renderer.ppi
    # Actually just draw at (0,0) which maps to center
    renderer.draw_ball(draw, 0, 0, ball_number)
    renderer.offset_x = orig_offset_x
    renderer.offset_y = orig_offset_y
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def get_table_metrics():
    """Return table dimensions and coordinate mapping info for the frontend."""
    renderer = get_renderer()
    config = renderer.config
    cx, cy = renderer.table_to_pixel(0, 0)
    return {
        "img_width": renderer.img_w,
        "img_height": renderer.img_h,
        "center_px": cx,
        "center_py": cy,
        "ppi": renderer.ppi,
        "half_width": config.half_width,
        "half_length": config.half_length,
        "ball_diameter": config.ball_diameter,
        "ball_radius_px": config.ball_radius * renderer.ppi,
        "max_ball_x": config.half_width - config.cushion_width - config.ball_radius,
        "max_ball_y": config.half_length - config.cushion_width - config.ball_radius,
    }


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
<title>Pool Table Editor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  #table-container, .table-ball, .ghost-sprite, .palette-ball, .palette-ghost, #path-svg { touch-action: none; }
  #table-container, #table-container * { -webkit-touch-callout: none; -webkit-user-select: none; user-select: none; }
  body {
    background: #1a1a1a;
    color: #eee;
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
    padding: 10px;
    user-select: none;
  }

  /* Editor wrapper — keeps palette and main-area aligned */
  #editor-wrapper {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }

  /* Palette */
  #palette {
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
    flex-wrap: wrap;
    justify-content: center;
    background: #2a2a2a;
    padding: 10px 16px;
    border-radius: 8px;
  }
  #palette .section-label {
    font-size: 11px;
    color: #888;
    align-self: center;
    margin-right: 2px;
    margin-left: 8px;
  }
  #palette .section-label:first-child { margin-left: 0; }
  .palette-ball {
    width: 40px;
    height: 40px;
    cursor: grab;
    transition: transform 0.1s;
    flex-shrink: 0;
  }
  .palette-ball:hover { transform: scale(1.15); }
  .palette-ball:active { cursor: grabbing; }
  .palette-ball.placed { opacity: 0.3; }

  /* Table area */
  #table-wrapper {
    position: relative;
    overflow: hidden;
    flex: 1;
  }
  #table-container {
    position: relative;
    display: inline-block;
    transform-origin: 0 0;
    margin: 0 auto;
  }
  #table-img {
    display: block;
    max-height: 80vh;
    width: auto;
  }

  /* Crop selection overlay */
  #crop-selection {
    position: absolute;
    border: 2px dashed rgba(255,200,50,0.9);
    background: rgba(255,200,50,0.1);
    pointer-events: none;
    display: none;
    z-index: 100;
  }

  /* Balls on table */
  .table-ball {
    position: absolute;
    cursor: grab;
    transition: filter 0.1s;
  }
  .table-ball:active { cursor: grabbing; }
  .table-ball.selected {
    filter: drop-shadow(0 0 6px rgba(255,255,255,0.9));
  }

  /* Main layout: side palette + table */
  #main-area {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    justify-content: center;
    width: 100%;
  }

  /* Side palette column */
  #side-palettes {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex-shrink: 0;
    width: 180px;
    margin-right: auto;
  }

  /* Side annotations palette */
  #annotations-palette {
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: #2a2a2a;
    padding: 10px 12px;
    border-radius: 8px;
    align-items: center;
  }
  #annotations-palette .section-label,
  #tools-palette .section-label {
    font-size: 10px;
    color: #888;
    margin-bottom: 2px;
  }

  /* Other tools palette */
  #tools-palette {
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: #2a2a2a;
    padding: 10px 12px;
    border-radius: 8px;
    align-items: center;
    width: 180px;
    flex-shrink: 0;
    margin-top: 8px;
  }

  /* Mode buttons */
  .mode-btn {
    background: #333;
    color: #ddd;
    border: 1px solid #555;
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .mode-btn:hover { background: #444; }
  .mode-btn.active { background: #665522; border-color: #aa8833; color: #fff; }

  /* Ghost palette item */
  .palette-ghost {
    cursor: grab;
    transition: transform 0.1s;
  }
  .palette-ghost:hover { transform: scale(1.15); }
  .palette-ghost:active { cursor: grabbing; }

  /* Ghost ball on table */
  .ghost-sprite {
    position: absolute;
    border: 2px dashed rgba(255,255,255,0.8);
    border-radius: 50%;
    cursor: grab;
    transition: box-shadow 0.1s;
  }
  .ghost-sprite:active { cursor: grabbing; }
  .ghost-sprite.selected {
    box-shadow: 0 0 8px rgba(255,255,255,0.7);
  }

  /* Path SVG overlay */
  #path-svg {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
  }
  #path-svg .path-line { pointer-events: stroke; cursor: pointer; }
  #path-svg .path-arrow { pointer-events: fill; cursor: pointer; }
  #path-svg .path-hitarea { pointer-events: stroke; cursor: pointer; }
  #path-svg .path-handle {
    pointer-events: all;
    cursor: grab;
    fill: rgba(255,255,255,0.9);
    stroke: #333;
    stroke-width: 1.5;
  }
  #path-svg .path-handle:hover { fill: #ffcc00; }
  #path-svg .path-group.selected .path-line { stroke: rgba(255,200,50,0.9); }
  #path-svg .path-group.selected .path-arrow { fill: rgba(255,200,50,0.9); }

  /* Output */
  #output {
    margin-top: 10px;
    background: #222;
    padding: 10px 16px;
    border-radius: 6px;
    font-family: monospace;
    font-size: 13px;
    max-width: 900px;
    width: 100%;
    white-space: pre-wrap;
    word-break: break-all;
    min-height: 40px;
    color: #0f0;
  }

  /* Coords display */
  #coords {
    position: fixed;
    bottom: 10px;
    right: 10px;
    background: rgba(0,0,0,0.8);
    padding: 4px 10px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 12px;
  }

  #help {
    position: fixed;
    bottom: 10px;
    left: 10px;
    background: rgba(0,0,0,0.8);
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 11px;
    color: #888;
    line-height: 1.5;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    body { padding: 4px; }
    #palette {
      gap: 3px;
      padding: 6px 8px;
      margin-bottom: 6px;
    }
    .palette-ball { width: 28px; height: 28px; }
    #palette .section-label { font-size: 9px; margin-left: 4px; margin-right: 1px; }
    #main-area { flex-direction: column; width: 100%; }
    #side-palettes {
      flex-direction: row;
      width: 100%;
      margin-right: 0;
      margin-bottom: 6px;
    }
    #annotations-palette, #tools-palette {
      flex-direction: row;
      width: auto;
      padding: 6px 8px;
    }
    #tools-palette { width: auto; margin-top: 0; }
    #table-img { max-height: 60vh; max-width: 100%; width: auto; }
    #table-wrapper { width: 100% !important; }
    #help { display: none; }
    #delete-btn {
      position: fixed !important;
      bottom: 20px;
      right: 20px;
      z-index: 9999;
      font-size: 14px !important;
      padding: 10px 20px !important;
    }
  }
</style>
</head>
<body>

<div id="editor-wrapper">
  <div id="palette">
    <span class="section-label">Cue</span>
    <img class="palette-ball" data-ball="0" src="data:image/png;base64,{{ ball_images[0] }}" title="Cue ball" />
    <span class="section-label">Solids</span>
    {% for n in range(1, 8) %}
    <img class="palette-ball" data-ball="{{ n }}" src="data:image/png;base64,{{ ball_images[n] }}" title="Ball {{ n }}" />
    {% endfor %}
    <span class="section-label">8</span>
    <img class="palette-ball" data-ball="8" src="data:image/png;base64,{{ ball_images[8] }}" title="8-ball" />
    <span class="section-label">Stripes</span>
    {% for n in range(9, 16) %}
    <img class="palette-ball" data-ball="{{ n }}" src="data:image/png;base64,{{ ball_images[n] }}" title="Ball {{ n }}" />
    {% endfor %}
  </div>
  <div id="main-area">
  <div id="side-palettes">
    <div id="annotations-palette">
      <span class="section-label">Annotations</span>
      <button class="mode-btn" id="path-mode-btn" title="Draw arrow paths (click and drag)">
        <svg width="28" height="16" viewBox="0 0 28 16">
          <line x1="2" y1="8" x2="20" y2="8" stroke="currentColor" stroke-width="2" stroke-dasharray="4,3"/>
          <polygon points="24,8 18,4 18,12" fill="currentColor"/>
        </svg>
      </button>
      <div class="palette-ghost" id="ghost-drag" title="Drag ghost ball onto table">
        <svg width="36" height="36" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="13" fill="none" stroke="rgba(255,255,255,0.8)" stroke-width="2" stroke-dasharray="4,3"/>
        </svg>
      </div>
    </div>
    <div id="tools-palette">
      <span class="section-label">Other Tools</span>
      <button class="mode-btn" id="crop-mode-btn" title="Crop and zoom (drag to select region)">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 2v4H2M6 6h12v12h4M18 22v-4h4M18 18H6V6"/>
        </svg>
      </button>
      <button class="mode-btn" id="reset-zoom-btn" title="Reset zoom to full table" style="font-size:10px;padding:4px 6px;">Reset</button>
      <button class="mode-btn" id="export-png-btn" title="Export as PNG in new tab" style="font-size:10px;padding:4px 6px;">To PNG</button>
      <button class="mode-btn" id="delete-btn" title="Delete selected item" style="font-size:10px;padding:4px 6px;background:#8b1a1a;color:#fff;border-color:#a33;display:none;">Delete</button>
    </div>
  </div>
  <div id="table-wrapper">
    <div id="table-container">
      <img id="table-img" src="data:image/png;base64,{{ table_image }}" />
      <svg id="path-svg"></svg>
      <div id="crop-selection"></div>
    </div>
  </div>
  </div>
</div>

<div id="output">Drag balls from the palette onto the table. Click to select, Delete to remove, Esc to deselect.</div>
<div id="coords"></div>
<div id="help">
  Drag from palette to place balls<br>
  Path mode: click+drag to draw arrows<br>
  Click to select &middot; Drag handles to adjust<br>
  Delete to remove &middot; Esc to deselect
</div>

<script>
const M = {{ metrics | tojson }};

const tableImg = document.getElementById('table-img');
const container = document.getElementById('table-container');
const output = document.getElementById('output');
const coordsEl = document.getElementById('coords');

// Scale: displayed pixels vs actual image pixels
let scale = 1;
function updateScale() {
  scale = tableImg.clientWidth / M.img_width;
}
setTimeout(updateScale, 100);

// Coordinate conversion
function pxToTable(dispX, dispY) {
  const imgX = dispX / scale;
  const imgY = dispY / scale;
  const tx = (imgX - M.center_px) / M.ppi;
  const ty = -(imgY - M.center_py) / M.ppi;
  return [Math.round(tx * 10) / 10, Math.round(ty * 10) / 10];
}
function tableToPx(tx, ty) {
  const imgX = M.center_px + tx * M.ppi;
  const imgY = M.center_py - ty * M.ppi;
  return [imgX * scale, imgY * scale];
}
function clampToTable(tx, ty) {
  tx = Math.max(-M.max_ball_x, Math.min(M.max_ball_x, tx));
  ty = Math.max(-M.max_ball_y, Math.min(M.max_ball_y, ty));
  return [Math.round(tx * 10) / 10, Math.round(ty * 10) / 10];
}
function resolveOverlaps(num, tx, ty) {
  // Push position away from other balls so no two overlap.
  // Minimum center-to-center distance is one ball diameter.
  const minDist = M.ball_diameter;
  for (let iter = 0; iter < 20; iter++) {
    let pushed = false;
    for (const [k, other] of Object.entries(placedBalls)) {
      if (parseInt(k) === num) continue;
      const dx = tx - other.tx;
      const dy = ty - other.ty;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < minDist) {
        pushed = true;
        if (dist < 0.01) {
          // Nearly coincident — nudge in arbitrary direction
          tx += minDist;
        } else {
          const overlap = minDist - dist;
          tx += (dx / dist) * overlap;
          ty += (dy / dist) * overlap;
        }
        // Re-clamp after push
        [tx, ty] = clampToTable(tx, ty);
      }
    }
    if (!pushed) break;
  }
  return [tx, ty];
}

// Ball size in display pixels
function ballDisplaySize() {
  return M.ball_radius_px * 2 * scale + 4 * scale;
}

// State: placed balls on the table
// { ballNum: { el, tx, ty } }
const placedBalls = {};
let selectedBall = null;

// State: paths (arrows)
const paths = []; // { id, x1, y1, x2, y2, group }
let nextPathId = 0;
let selectedPath = null;
let pathMode = false;
const pathSvg = document.getElementById('path-svg');

// State: ghost balls
const ghosts = []; // { id, tx, ty, el }
let nextGhostId = 0;
let selectedGhost = null;

// Prevent long-press context menu on mobile
container.addEventListener('contextmenu', (e) => e.preventDefault());

// Convert screen coords to container-internal display coords
function screenToContainer(clientX, clientY) {
  const containerRect = container.getBoundingClientRect();
  const cx = clientX - containerRect.left;
  const cy = clientY - containerRect.top;
  const dispX = cx / zoomScale;
  const dispY = cy / zoomScale;
  return [dispX, dispY];
}

// --- Palette drag (pointer-based, works on touch + mouse) ---
let paletteDragData = null;
let paletteDragClone = null;

let paletteDragIsTouch = false;

function startPaletteDrag(e, data, sourceEl) {
  e.preventDefault();
  paletteDragData = data;
  paletteDragIsTouch = e.pointerType === 'touch';
  const offset = paletteDragIsTouch ? TOUCH_OFFSET * 2 : 0;
  paletteDragClone = sourceEl.cloneNode(true);
  paletteDragClone.style.position = 'fixed';
  paletteDragClone.style.pointerEvents = 'none';
  paletteDragClone.style.zIndex = '9999';
  paletteDragClone.style.opacity = '0.8';
  paletteDragClone.style.width = '40px';
  paletteDragClone.style.height = '40px';
  paletteDragClone.style.left = (e.clientX - 20 - offset) + 'px';
  paletteDragClone.style.top = (e.clientY - 20 - offset) + 'px';
  document.body.appendChild(paletteDragClone);
}

document.addEventListener('pointermove', (e) => {
  if (!paletteDragClone) return;
  const offset = paletteDragIsTouch ? TOUCH_OFFSET * 2 : 0;
  paletteDragClone.style.left = (e.clientX - 20 - offset) + 'px';
  paletteDragClone.style.top = (e.clientY - 20 - offset) + 'px';
});

let justDroppedFromPalette = false;
document.addEventListener('pointerup', (e) => {
  if (!paletteDragClone) return;
  paletteDragClone.remove();
  paletteDragClone = null;

  // Check if dropped over the table (use offset position for touch)
  const offset = paletteDragIsTouch ? TOUCH_OFFSET * 2 : 0;
  const dropX = e.clientX - offset;
  const dropY = e.clientY - offset;
  const containerRect = container.getBoundingClientRect();
  if (dropX >= containerRect.left && dropX <= containerRect.right &&
      dropY >= containerRect.top && dropY <= containerRect.bottom) {
    const [dispX, dispY] = screenToContainer(dropX, dropY);
    const [tx, ty] = clampToTable(...pxToTable(dispX, dispY));
    if (paletteDragData === 'ghost') {
      placeGhost(tx, ty);
    } else {
      const ballNum = parseInt(paletteDragData);
      if (!isNaN(ballNum)) {
        let [bx, by] = resolveOverlaps(ballNum, tx, ty);
        placeBall(ballNum, bx, by);
      }
    }
    justDroppedFromPalette = true;
  }
  paletteDragData = null;
});

document.querySelectorAll('.palette-ball').forEach(img => {
  img.addEventListener('pointerdown', (e) => {
    startPaletteDrag(e, img.dataset.ball, img);
  });
});

function placeBall(num, tx, ty) {
  // Remove existing instance
  if (placedBalls[num]) {
    placedBalls[num].el.remove();
    delete placedBalls[num];
  }

  // Create element
  const paletteImg = document.querySelector(`.palette-ball[data-ball="${num}"]`);
  const el = document.createElement('img');
  el.src = paletteImg.src;
  el.className = 'table-ball';
  el.dataset.ball = num;
  const size = ballDisplaySize();
  el.style.width = size + 'px';
  el.style.height = size + 'px';
  el.draggable = false;

  container.appendChild(el);
  const entry = { el, tx, ty };
  placedBalls[num] = entry;
  positionBall(entry);

  // Mark palette as placed
  paletteImg.classList.add('placed');

  // Selection is handled in makeTableDraggable pointerup

  // Make draggable on table
  makeTableDraggable(el, entry);

  selectBall(num);
  exportCLI();
}

function positionBall(entry) {
  const [dpx, dpy] = tableToPx(entry.tx, entry.ty);
  const size = ballDisplaySize();
  entry.el.style.left = (dpx - size / 2) + 'px';
  entry.el.style.top = (dpy - size / 2) + 'px';
}

function selectBall(num) {
  deselectAll();
  selectedBall = num;
  if (placedBalls[num]) {
    placedBalls[num].el.classList.add('selected');
  }
  updateDeleteBtn();
}

function selectPath(id) {
  deselectAll();
  selectedPath = id;
  const p = paths.find(p => p.id === id);
  if (p) {
    p.group.classList.add('selected');
    updatePathHandles(p, true);
  }
  updateDeleteBtn();
}

function selectGhost(id) {
  deselectAll();
  selectedGhost = id;
  const g = ghosts.find(g => g.id === id);
  if (g) g.el.classList.add('selected');
  updateDeleteBtn();
}

const deleteBtn = document.getElementById('delete-btn');
function updateDeleteBtn() {
  deleteBtn.style.display = (selectedBall !== null || selectedGhost !== null || selectedPath !== null) ? '' : 'none';
}
deleteBtn.addEventListener('click', () => {
  if (selectedGhost !== null) removeGhost(selectedGhost);
  else if (selectedPath !== null) removePath(selectedPath);
  else if (selectedBall !== null) removeBall(selectedBall);
  updateDeleteBtn();
});

function deselectAll() {
  if (selectedBall !== null && placedBalls[selectedBall]) {
    placedBalls[selectedBall].el.classList.remove('selected');
  }
  selectedBall = null;
  if (selectedPath !== null) {
    const p = paths.find(p => p.id === selectedPath);
    if (p) {
      p.group.classList.remove('selected');
      updatePathHandles(p, false);
    }
  }
  selectedPath = null;
  if (selectedGhost !== null) {
    const g = ghosts.find(g => g.id === selectedGhost);
    if (g) g.el.classList.remove('selected');
  }
  selectedGhost = null;
  updateDeleteBtn();
}

function removeBall(num) {
  if (!placedBalls[num]) return;
  placedBalls[num].el.remove();
  delete placedBalls[num];
  const paletteImg = document.querySelector(`.palette-ball[data-ball="${num}"]`);
  if (paletteImg) paletteImg.classList.remove('placed');
  if (selectedBall === num) selectedBall = null;
  exportCLI();
}

function removePath(id) {
  const idx = paths.findIndex(p => p.id === id);
  if (idx === -1) return;
  paths[idx].group.remove();
  paths.splice(idx, 1);
  if (selectedPath === id) selectedPath = null;
  exportCLI();
}

function removeGhost(id) {
  const idx = ghosts.findIndex(g => g.id === id);
  if (idx === -1) return;
  ghosts[idx].el.remove();
  ghosts.splice(idx, 1);
  if (selectedGhost === id) selectedGhost = null;
  exportCLI();
}

// Touch offset: shift sprite up-left so it's visible above finger
const TOUCH_OFFSET = 21; // pixels in display coords
let anyDragActive = false; // global flag to block pinch/pan during drags

// Table dragging
function makeTableDraggable(el, entry) {
  let dragging = false;
  let startX, startY, origLeft, origTop;
  let moved = false;

  el.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true;
    anyDragActive = true;
    moved = false;
    const isTouch = e.pointerType === 'touch';
    const offset = isTouch ? TOUCH_OFFSET / zoomScale : 0;
    startX = e.clientX;
    startY = e.clientY;
    origLeft = (parseFloat(el.style.left) || 0) - offset;
    origTop = (parseFloat(el.style.top) || 0) - offset;
    if (isTouch) { el.style.left = origLeft + 'px'; el.style.top = origTop + 'px'; moved = true; }
    e.preventDefault();
  });

  document.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = (e.clientX - startX) / zoomScale;
    const dy = (e.clientY - startY) / zoomScale;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
    el.style.left = (origLeft + dx) + 'px';
    el.style.top = (origTop + dy) + 'px';

    // Update table coords with boundary + overlap clamping
    const size = ballDisplaySize();
    const centerX = parseFloat(el.style.left) + size / 2;
    const centerY = parseFloat(el.style.top) + size / 2;
    let [tx, ty] = clampToTable(...pxToTable(centerX, centerY));
    const ballNum = parseInt(el.dataset.ball);
    [tx, ty] = resolveOverlaps(ballNum, tx, ty);
    entry.tx = tx;
    entry.ty = ty;
    positionBall(entry);
    coordsEl.textContent = `Ball ${ballNum}: (${tx}, ${ty})`;
  });

  document.addEventListener('pointerup', () => {
    if (dragging) {
      dragging = false;
      anyDragActive = false;
      if (moved) exportCLI();
      const bn = parseInt(el.dataset.ball);
      if (!isNaN(bn)) selectBall(bn);
    }
  });
}

// Keyboard
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    deselectAll();
    if (pathMode) togglePathMode(false);
    if (cropMode) { cropMode = false; cropModeBtn.classList.remove('active'); container.style.cursor = ''; }
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedGhost !== null) removeGhost(selectedGhost);
    else if (selectedPath !== null) removePath(selectedPath);
    else if (selectedBall !== null) removeBall(selectedBall);
  }
});

// Click on table background to deselect
container.addEventListener('click', (e) => {
  if (justDroppedFromPalette) { justDroppedFromPalette = false; return; }
  if (e.target === tableImg || e.target === container) {
    deselectAll();
  }
});

// Mouse coords
container.addEventListener('pointermove', (e) => {
  const [dx, dy] = screenToContainer(e.clientX, e.clientY);
  const [tx, ty] = pxToTable(dx, dy);
  coordsEl.textContent = `(${tx}, ${ty})`;
});

// ========== GHOST BALL DRAG FROM PALETTE ==========
const ghostDrag = document.getElementById('ghost-drag');
ghostDrag.addEventListener('pointerdown', (e) => {
  startPaletteDrag(e, 'ghost', ghostDrag);
});

function placeGhost(tx, ty) {
  const id = nextGhostId++;
  const size = ballDisplaySize();
  const el = document.createElement('div');
  el.className = 'ghost-sprite';
  el.style.width = size + 'px';
  el.style.height = size + 'px';
  container.appendChild(el);

  const entry = { id, tx, ty, el };
  ghosts.push(entry);
  positionGhost(entry);

  el.addEventListener('click', (e) => {
    e.stopPropagation();
    selectGhost(id);
  });

  // Make draggable
  makeGhostDraggable(el, entry);
  selectGhost(id);
  exportCLI();
}

function positionGhost(entry) {
  const [dpx, dpy] = tableToPx(entry.tx, entry.ty);
  const size = ballDisplaySize();
  entry.el.style.left = (dpx - size / 2) + 'px';
  entry.el.style.top = (dpy - size / 2) + 'px';
}

function makeGhostDraggable(el, entry) {
  let dragging = false;
  let startX, startY, origLeft, origTop;
  let moved = false;

  el.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true;
    anyDragActive = true;
    moved = false;
    const isTouch = e.pointerType === 'touch';
    const offset = isTouch ? TOUCH_OFFSET / zoomScale : 0;
    startX = e.clientX;
    startY = e.clientY;
    origLeft = (parseFloat(el.style.left) || 0) - offset;
    origTop = (parseFloat(el.style.top) || 0) - offset;
    if (isTouch) { el.style.left = origLeft + 'px'; el.style.top = origTop + 'px'; moved = true; }
    e.preventDefault();
  });

  document.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = (e.clientX - startX) / zoomScale;
    const dy = (e.clientY - startY) / zoomScale;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
    el.style.left = (origLeft + dx) + 'px';
    el.style.top = (origTop + dy) + 'px';
    const size = ballDisplaySize();
    const centerX = parseFloat(el.style.left) + size / 2;
    const centerY = parseFloat(el.style.top) + size / 2;
    const [tx, ty] = clampToTable(...pxToTable(centerX, centerY));
    entry.tx = tx;
    entry.ty = ty;
    positionGhost(entry);
    coordsEl.textContent = `Ghost: (${tx}, ${ty})`;
  });

  document.addEventListener('pointerup', () => {
    if (dragging) {
      dragging = false;
      anyDragActive = false;
      if (moved) exportCLI();
      selectGhost(entry.id);
    }
  });
}

// ========== PATH MODE ==========
const pathModeBtn = document.getElementById('path-mode-btn');
pathModeBtn.addEventListener('click', () => togglePathMode());

function togglePathMode(force) {
  pathMode = force !== undefined ? force : !pathMode;
  pathModeBtn.classList.toggle('active', pathMode);
  container.style.cursor = pathMode ? 'crosshair' : '';
}

function resizePathSvg() {
  pathSvg.setAttribute('width', tableImg.clientWidth);
  pathSvg.setAttribute('height', tableImg.clientHeight);
}
tableImg.onload = () => { updateScale(); resizePathSvg(); };
setTimeout(resizePathSvg, 100);

// Drawing a new path: mousedown on table in path mode
let pathDrawing = null; // { x1, y1, tempLine, tempArrow }
container.addEventListener('pointerdown', (e) => {
  if (!pathMode) return;
  if (e.target !== tableImg && !e.target.closest('#path-svg')) return;
  if (e.button !== 0) return;

  const [dx, dy] = screenToContainer(e.clientX, e.clientY);
  const [tx, ty] = clampToTable(...pxToTable(dx, dy));
  const [px, py] = tableToPx(tx, ty);

  // Create temp line
  const sw = 2 / zoomScale;
  const line = svgEl('line', {
    x1: px, y1: py, x2: px, y2: py,
    stroke: 'white', 'stroke-width': sw, 'stroke-dasharray': `${8/zoomScale},${6/zoomScale}`,
    'pointer-events': 'none',
  });
  const arrow = svgEl('polygon', {
    points: `${px},${py} ${px},${py} ${px},${py}`,
    fill: 'white', 'pointer-events': 'none',
  });
  pathSvg.appendChild(line);
  pathSvg.appendChild(arrow);
  pathDrawing = { tx1: tx, ty1: ty, line, arrow };
  e.preventDefault();
});

document.addEventListener('pointermove', (e) => {
  if (!pathDrawing) return;
  const [dx, dy] = screenToContainer(e.clientX, e.clientY);
  const [tx, ty] = clampToTable(...pxToTable(dx, dy));
  const [px1, py1] = tableToPx(pathDrawing.tx1, pathDrawing.ty1);
  const [px2, py2] = tableToPx(tx, ty);
  pathDrawing.line.setAttribute('x2', px2);
  pathDrawing.line.setAttribute('y2', py2);
  pathDrawing.arrow.setAttribute('points', arrowPoints(px1, py1, px2, py2));
});

document.addEventListener('pointerup', (e) => {
  if (!pathDrawing) return;
  const [dx2, dy2] = screenToContainer(e.clientX, e.clientY);
  const [tx2, ty2] = clampToTable(...pxToTable(dx2, dy2));
  // Remove temp elements
  pathDrawing.line.remove();
  pathDrawing.arrow.remove();
  // Only create if path has some length; otherwise treat as a deselect click
  const dx = tx2 - pathDrawing.tx1;
  const dy = ty2 - pathDrawing.ty1;
  if (Math.sqrt(dx*dx + dy*dy) > 0.5) {
    createPath(pathDrawing.tx1, pathDrawing.ty1, tx2, ty2);
    togglePathMode(false);
  } else {
    deselectAll();
  }
  pathDrawing = null;
});

function createPath(x1, y1, x2, y2) {
  const id = nextPathId++;
  const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  group.classList.add('path-group');

  // Wide invisible hit area for clicking
  const hitarea = svgEl('line', {
    class: 'path-hitarea',
    'stroke-width': 14, stroke: 'transparent',
  });
  const line = svgEl('line', {
    class: 'path-line',
    'stroke-width': 2, stroke: 'white', 'stroke-dasharray': '8,6',
  });
  const arrow = svgEl('polygon', {
    class: 'path-arrow', fill: 'white',
  });
  // Handles (hidden by default, shown on select)
  const h1 = svgEl('circle', { class: 'path-handle', r: 6, style: 'display:none' });
  const h2 = svgEl('circle', { class: 'path-handle', r: 6, style: 'display:none' });

  group.appendChild(hitarea);
  group.appendChild(line);
  group.appendChild(arrow);
  group.appendChild(h1);
  group.appendChild(h2);
  pathSvg.appendChild(group);

  const p = { id, x1, y1, x2, y2, group, line, arrow, hitarea, h1, h2 };
  paths.push(p);
  renderPath(p);

  // Click to select + drag to move whole path
  let pathDragging = false;
  let pathDragStart = null;
  [hitarea, line, arrow].forEach(el => {
    el.addEventListener('pointerdown', (e) => {
      e.stopPropagation();
      e.preventDefault();
      selectPath(id);
      pathDragging = true;
      anyDragActive = true;
      const [dx, dy] = screenToContainer(e.clientX, e.clientY);
      const isTouch = e.pointerType === 'touch';
      const offset = isTouch ? TOUCH_OFFSET : 0;
      pathDragStart = { cx: dx - offset, cy: dy - offset, x1: p.x1, y1: p.y1, x2: p.x2, y2: p.y2 };
    });
  });
  document.addEventListener('pointermove', (e) => {
    if (!pathDragging || !pathDragStart) return;
    const [dx, dy] = screenToContainer(e.clientX, e.clientY);
    const isTouch = e.pointerType === 'touch';
    const offset = isTouch ? TOUCH_OFFSET : 0;
    const [startTx, startTy] = pxToTable(pathDragStart.cx, pathDragStart.cy);
    const [curTx, curTy] = pxToTable(dx - offset, dy - offset);
    let dtx = curTx - startTx;
    let dty = curTy - startTy;
    // Clamp so neither endpoint exceeds table boundaries
    const nx1 = pathDragStart.x1 + dtx, ny1 = pathDragStart.y1 + dty;
    const nx2 = pathDragStart.x2 + dtx, ny2 = pathDragStart.y2 + dty;
    const maxX = M.max_ball_x, maxY = M.max_ball_y;
    if (nx1 < -maxX) dtx += (-maxX - nx1);
    if (nx1 > maxX) dtx += (maxX - nx1);
    if (nx2 < -maxX) dtx += (-maxX - nx2);
    if (nx2 > maxX) dtx += (maxX - nx2);
    if (ny1 < -maxY) dty += (-maxY - ny1);
    if (ny1 > maxY) dty += (maxY - ny1);
    if (ny2 < -maxY) dty += (-maxY - ny2);
    if (ny2 > maxY) dty += (maxY - ny2);
    p.x1 = pathDragStart.x1 + dtx;
    p.y1 = pathDragStart.y1 + dty;
    p.x2 = pathDragStart.x2 + dtx;
    p.y2 = pathDragStart.y2 + dty;
    renderPath(p);
  });
  document.addEventListener('pointerup', () => {
    if (pathDragging) {
      pathDragging = false;
      anyDragActive = false;
      pathDragStart = null;
      exportCLI();
    }
  });

  // Handle dragging
  setupHandleDrag(h1, p, 'start');
  setupHandleDrag(h2, p, 'end');

  selectPath(id);
  exportCLI();
}

function renderPath(p) {
  const [px1, py1] = tableToPx(p.x1, p.y1);
  const [px2, py2] = tableToPx(p.x2, p.y2);
  const sw = 2 / zoomScale;
  setAttrs(p.line, { x1: px1, y1: py1, x2: px2, y2: py2, 'stroke-width': sw, 'stroke-dasharray': `${8/zoomScale},${6/zoomScale}` });
  setAttrs(p.hitarea, { x1: px1, y1: py1, x2: px2, y2: py2, 'stroke-width': 14 / zoomScale });
  p.arrow.setAttribute('points', arrowPoints(px1, py1, px2, py2));
  setAttrs(p.h1, { cx: px1, cy: py1, r: 6 / zoomScale });
  setAttrs(p.h2, { cx: px2, cy: py2, r: 6 / zoomScale });
}

function updatePathHandles(p, show) {
  p.h1.style.display = show ? '' : 'none';
  p.h2.style.display = show ? '' : 'none';
}

function setupHandleDrag(handle, p, which) {
  let dragging = false;
  let isTouch = false;
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true;
    anyDragActive = true;
    isTouch = e.pointerType === 'touch';
    e.stopPropagation();
    e.preventDefault();
  });
  document.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const [dx, dy] = screenToContainer(e.clientX, e.clientY);
    const offset = isTouch ? TOUCH_OFFSET : 0;
    const [tx, ty] = clampToTable(...pxToTable(dx - offset, dy - offset));
    if (which === 'start') { p.x1 = tx; p.y1 = ty; }
    else { p.x2 = tx; p.y2 = ty; }
    renderPath(p);
    coordsEl.textContent = `Path ${which}: (${tx}, ${ty})`;
  });
  document.addEventListener('pointerup', () => {
    if (dragging) { dragging = false; anyDragActive = false; exportCLI(); }
  });
}

// SVG helpers
function svgEl(tag, attrs) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}
function setAttrs(el, attrs) {
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
}
function arrowPoints(px1, py1, px2, py2) {
  const dx = px2 - px1, dy = py2 - py1;
  const len = Math.sqrt(dx*dx + dy*dy);
  if (len < 1) return `${px2},${py2} ${px2},${py2} ${px2},${py2}`;
  const ux = dx/len, uy = dy/len;
  const s = 10 / zoomScale;
  const w1x = px2 - ux*s + (-uy)*s*0.5;
  const w1y = py2 - uy*s + (ux)*s*0.5;
  const w2x = px2 - ux*s - (-uy)*s*0.5;
  const w2y = py2 - uy*s - (ux)*s*0.5;
  return `${px2},${py2} ${w1x},${w1y} ${w2x},${w2y}`;
}

// Export CLI
function exportCLI() {
  const parts = ['python -m pooltool.cli --ppi 24'];
  const nums = Object.keys(placedBalls).map(Number).sort((a, b) => a - b);
  nums.forEach(n => {
    const b = placedBalls[n];
    parts.push(`-b ${n}:${b.tx},${b.ty}`);
  });
  ghosts.forEach(g => {
    parts.push(`-g ${g.tx},${g.ty}`);
  });
  paths.forEach(p => {
    parts.push(`-p ${p.x1},${p.y1}:${p.x2},${p.y2}`);
  });
  if (nums.length === 0 && paths.length === 0 && ghosts.length === 0) {
    output.textContent = 'No items placed.';
    return;
  }
  output.textContent = parts.join(' \\\n  ');
}

// ========== CROP / ZOOM ==========
const cropModeBtn = document.getElementById('crop-mode-btn');
const resetZoomBtn = document.getElementById('reset-zoom-btn');
const cropSelection = document.getElementById('crop-selection');
const tableWrapper = document.getElementById('table-wrapper');
let cropMode = false;
let cropDragging = false;
let cropStartX, cropStartY;

// Current zoom state
let zoomScale = 1;
let zoomOffsetX = 0;
let zoomOffsetY = 0;
let zoomSelW = 0;
let zoomSelH = 0;

cropModeBtn.addEventListener('click', () => {
  cropMode = !cropMode;
  cropModeBtn.classList.toggle('active', cropMode);
  if (pathMode) togglePathMode(false);
  container.style.cursor = cropMode ? 'crosshair' : '';
});

resetZoomBtn.addEventListener('click', resetZoom);

function resetZoom() {
  zoomScale = 1;
  zoomOffsetX = 0;
  zoomOffsetY = 0;
  applyZoom();
}

function applyZoom() {
  container.style.transform = `scale(${zoomScale}) translate(${-zoomOffsetX}px, ${-zoomOffsetY}px)`;
  if (zoomScale === 1) {
    tableWrapper.style.width = '';
    tableWrapper.style.height = '';
    container.style.margin = '0 auto';
  } else {
    // Size wrapper to show the visible region
    const visW = zoomSelW > 0 ? zoomSelW : (tableImg.clientWidth - zoomOffsetX);
    const visH = zoomSelH > 0 ? zoomSelH : (tableImg.clientHeight - zoomOffsetY);
    tableWrapper.style.width = (visW * zoomScale) + 'px';
    tableWrapper.style.height = (visH * zoomScale) + 'px';
    container.style.margin = '0';
  }
  paths.forEach(renderPath);
}

// Crop selection drawing
container.addEventListener('pointerdown', (e) => {
  if (!cropMode) return;
  if (e.button !== 0) return;
  cropDragging = true;
  [cropStartX, cropStartY] = screenToContainer(e.clientX, e.clientY);
  cropSelection.style.display = 'block';
  cropSelection.style.left = cropStartX + 'px';
  cropSelection.style.top = cropStartY + 'px';
  cropSelection.style.width = '0px';
  cropSelection.style.height = '0px';
  e.preventDefault();
  e.stopPropagation();
});

document.addEventListener('pointermove', (e) => {
  if (!cropDragging) return;
  const [curX, curY] = screenToContainer(e.clientX, e.clientY);
  const x = Math.min(cropStartX, curX);
  const y = Math.min(cropStartY, curY);
  const w = Math.abs(curX - cropStartX);
  const h = Math.abs(curY - cropStartY);
  cropSelection.style.left = x + 'px';
  cropSelection.style.top = y + 'px';
  cropSelection.style.width = w + 'px';
  cropSelection.style.height = h + 'px';
});

document.addEventListener('pointerup', (e) => {
  if (!cropDragging) return;
  cropDragging = false;
  cropSelection.style.display = 'none';

  const [curX, curY] = screenToContainer(e.clientX, e.clientY);
  const selX = Math.min(cropStartX, curX);
  const selY = Math.min(cropStartY, curY);
  const selW = Math.abs(curX - cropStartX);
  const selH = Math.abs(curY - cropStartY);

  // Only zoom if selection is meaningful
  if (selW < 10 || selH < 10) return;

  // Scale to fill horizontal space, but cap height at viewport
  const availableW = tableWrapper.parentElement.clientWidth;
  const maxH = window.innerHeight * 0.75; // cap at 75% viewport height
  const hScale = availableW / selW;
  const vScale = maxH / selH;
  const fitScale = Math.min(hScale, vScale);
  const newZoom = fitScale;

  // The selection top-left becomes the new offset
  const newOffsetX = selX;
  const newOffsetY = selY;

  // Store the selected region dimensions for wrapper sizing
  zoomSelW = selW;
  zoomSelH = selH;

  zoomScale = newZoom;
  zoomOffsetX = newOffsetX;
  zoomOffsetY = newOffsetY;
  applyZoom();

  // Exit crop mode
  cropMode = false;
  cropModeBtn.classList.remove('active');
  container.style.cursor = '';
});

// ========== PINCH ZOOM (mobile) ==========
const activePointers = new Map();

container.addEventListener('pointerdown', (e) => {
  activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
}, true);

document.addEventListener('pointerup', (e) => {
  activePointers.delete(e.pointerId);
});
document.addEventListener('pointercancel', (e) => {
  activePointers.delete(e.pointerId);
});

let pinchStartDist = null;
let pinchStartZoom = null;
let pinchMidX = null;
let pinchMidY = null;

document.addEventListener('pointermove', (e) => {
  if (!activePointers.has(e.pointerId)) return;
  activePointers.set(e.pointerId, { x: e.clientX, y: e.clientY });

  if (activePointers.size === 2 && !anyDragActive) {
    const pts = [...activePointers.values()];
    const dx = pts[1].x - pts[0].x;
    const dy = pts[1].y - pts[0].y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const midX = (pts[0].x + pts[1].x) / 2;
    const midY = (pts[0].y + pts[1].y) / 2;

    if (pinchStartDist === null) {
      // Start of pinch
      pinchStartDist = dist;
      pinchStartZoom = zoomScale;
      // Store midpoint in container coords for zoom center
      const [cx, cy] = screenToContainer(midX, midY);
      pinchMidX = cx;
      pinchMidY = cy;
    } else {
      // Ongoing pinch — scale relative to start
      const newZoom = Math.max(0.5, Math.min(10, pinchStartZoom * (dist / pinchStartDist)));

      // Zoom toward the pinch midpoint
      // The midpoint should stay at the same screen position
      zoomOffsetX = pinchMidX - (pinchMidX - zoomOffsetX) * (zoomScale / newZoom);
      zoomOffsetY = pinchMidY - (pinchMidY - zoomOffsetY) * (zoomScale / newZoom);

      zoomScale = newZoom;
      zoomSelW = 0;
      zoomSelH = 0;
      applyZoom();
    }
    e.preventDefault();
  }
});

// Reset pinch state when a finger lifts
document.addEventListener('pointerup', (e) => {
  if (activePointers.size < 2) {
    pinchStartDist = null;
    pinchStartZoom = null;
  }
});

// ========== PAN (one-finger drag when zoomed) ==========
let panActive = false;
let panStartX = 0, panStartY = 0;
let panOrigOffsetX = 0, panOrigOffsetY = 0;

container.addEventListener('pointerdown', (e) => {
  if (zoomScale <= 1) return;
  if (activePointers.size > 1) return;
  if (anyDragActive) return;
  // Don't pan if interacting with a ball, ghost, path, or in crop/path mode
  if (cropMode || pathMode) return;
  if (e.target.classList.contains('table-ball') || e.target.classList.contains('ghost-sprite')) return;
  if (e.target.closest('#path-svg')) return;
  panActive = true;
  panStartX = e.clientX;
  panStartY = e.clientY;
  panOrigOffsetX = zoomOffsetX;
  panOrigOffsetY = zoomOffsetY;
  e.preventDefault();
});

document.addEventListener('pointermove', (e) => {
  if (!panActive) return;
  if (activePointers.size > 1) { panActive = false; return; }
  const dx = (e.clientX - panStartX) / zoomScale;
  const dy = (e.clientY - panStartY) / zoomScale;
  zoomOffsetX = panOrigOffsetX - dx;
  zoomOffsetY = panOrigOffsetY - dy;
  zoomSelW = 0;
  zoomSelH = 0;
  applyZoom();
});

document.addEventListener('pointerup', (e) => {
  panActive = false;
});

// Export to PNG
document.getElementById('export-png-btn').addEventListener('click', () => {
  const natW = tableImg.naturalWidth;
  const natH = tableImg.naturalHeight;
  const s = natW / tableImg.clientWidth; // display px to image px

  // Helper: table coords to image pixel coords
  function t2i(tx, ty) {
    const imgX = M.center_px + tx * M.ppi;
    const imgY = M.center_py - ty * M.ppi;
    return [imgX, imgY];
  }

  // Determine crop region in image pixels
  let cropX = 0, cropY = 0, cropW = natW, cropH = natH;
  if (zoomScale !== 1) {
    // What's visible = the wrapper size / zoomScale (in container display px)
    const visW = tableWrapper.clientWidth / zoomScale;
    const visH = tableWrapper.clientHeight / zoomScale;
    cropX = zoomOffsetX * s;
    cropY = zoomOffsetY * s;
    cropW = visW * s;
    cropH = visH * s;
    // Clamp to image bounds
    if (cropX + cropW > natW) cropW = natW - cropX;
    if (cropY + cropH > natH) cropH = natH - cropY;
    if (cropX < 0) { cropW += cropX; cropX = 0; }
    if (cropY < 0) { cropH += cropY; cropY = 0; }
  }

  const outW = Math.round(cropW);
  const outH = Math.round(cropH);
  const canvas = document.createElement('canvas');
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext('2d');

  // Scale factor for strokes/arrows: keep them proportional to output size
  // When cropped, elements should look the same relative thickness as in full PNG
  const rs = cropW / natW; // render scale: 1 when full, <1 when cropped

  // Draw table (cropped region)
  ctx.drawImage(tableImg, cropX, cropY, cropW, cropH, 0, 0, outW, outH);

  // Offset for drawing: shift everything by -crop origin
  const ox = -cropX;
  const oy = -cropY;

  // Draw balls
  for (const [num, b] of Object.entries(placedBalls)) {
    const img = document.querySelector(`.palette-ball[data-ball="${num}"]`);
    const size = parseFloat(b.el.style.width) * s;
    const x = parseFloat(b.el.style.left) * s + ox;
    const y = parseFloat(b.el.style.top) * s + oy;
    ctx.drawImage(img, x, y, size, size);
  }

  // Draw ghosts
  for (const g of ghosts) {
    const gsize = parseFloat(g.el.style.width) * s;
    const gcx = (parseFloat(g.el.style.left) + parseFloat(g.el.style.width) / 2) * s + ox;
    const gcy = (parseFloat(g.el.style.top) + parseFloat(g.el.style.width) / 2) * s + oy;
    const r = gsize / 2 - 2 * s * rs;
    ctx.beginPath();
    ctx.arc(gcx, gcy, r, 0, 2 * Math.PI);
    ctx.strokeStyle = 'rgba(255,255,255,0.8)';
    ctx.lineWidth = 2 * s * rs;
    ctx.setLineDash([4 * s * rs, 3 * s * rs]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // Draw paths
  for (const p of paths) {
    const [ix1, iy1] = t2i(p.x1, p.y1);
    const [ix2, iy2] = t2i(p.x2, p.y2);
    const x1 = ix1 + ox, y1 = iy1 + oy;
    const x2 = ix2 + ox, y2 = iy2 + oy;
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 1) continue;
    const ux = dx / len, uy = dy / len;
    const arrowSize = 10 * s * rs;

    // Dotted line
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2 - ux * arrowSize, y2 - uy * arrowSize);
    ctx.strokeStyle = 'rgba(255,255,255,0.85)';
    ctx.lineWidth = 2 * s * rs;
    ctx.setLineDash([8 * s * rs, 6 * s * rs]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Arrowhead
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - ux * arrowSize - uy * arrowSize * 0.5, y2 - uy * arrowSize + ux * arrowSize * 0.5);
    ctx.lineTo(x2 - ux * arrowSize + uy * arrowSize * 0.5, y2 - uy * arrowSize - ux * arrowSize * 0.5);
    ctx.closePath();
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.fill();
  }

  // Open in new tab
  canvas.toBlob((blob) => {
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  }, 'image/png');
});

// Reposition on resize
window.addEventListener('resize', () => {
  updateScale();
  resizePathSvg();
  Object.values(placedBalls).forEach(positionBall);
  ghosts.forEach(positionGhost);
  paths.forEach(renderPath);
  if (zoomScale !== 1) applyZoom();
});
</script>
</body>
</html>
"""


@app.route("/")
def index():
    table_image = get_table_image_data()
    metrics = get_table_metrics()

    # Pre-render all ball images server-side
    ball_images = {}
    for n in range(0, 16):
        ball_images[n] = render_ball_image(n)

    return render_template_string(
        HTML_TEMPLATE,
        table_image=table_image,
        metrics=metrics,
        ball_images=ball_images,
    )


def run(table_size="9foot", ppi=24.0, port=5555):
    global TABLE_SIZE, PPI
    TABLE_SIZE = table_size
    PPI = ppi
    print(f"Starting interactive editor at http://localhost:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    run()
