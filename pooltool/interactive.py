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
<title>Pool Table Editor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
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

  /* Palette */
  #palette {
    display: flex;
    gap: 6px;
    margin-bottom: 10px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 1000px;
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
  #table-container {
    position: relative;
    display: inline-block;
  }
  #table-img {
    display: block;
    max-height: 80vh;
    width: auto;
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
</style>
</head>
<body>

<div id="palette">
  <span class="section-label">Cue</span>
  <img class="palette-ball" data-ball="0" src="data:image/png;base64,{{ ball_images[0] }}" draggable="true" title="Cue ball" />
  <span class="section-label">Solids</span>
  {% for n in range(1, 8) %}
  <img class="palette-ball" data-ball="{{ n }}" src="data:image/png;base64,{{ ball_images[n] }}" draggable="true" title="Ball {{ n }}" />
  {% endfor %}
  <span class="section-label">8</span>
  <img class="palette-ball" data-ball="8" src="data:image/png;base64,{{ ball_images[8] }}" draggable="true" title="8-ball" />
  <span class="section-label">Stripes</span>
  {% for n in range(9, 16) %}
  <img class="palette-ball" data-ball="{{ n }}" src="data:image/png;base64,{{ ball_images[n] }}" draggable="true" title="Ball {{ n }}" />
  {% endfor %}
</div>

<div id="table-container">
  <img id="table-img" src="data:image/png;base64,{{ table_image }}" />
</div>

<div id="output">Drag balls from the palette onto the table. Click to select, Delete to remove, Esc to deselect.</div>
<div id="coords"></div>
<div id="help">
  Drag from palette to place<br>
  Drag on table to move<br>
  Click to select &middot; Delete to remove<br>
  Esc to deselect
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
tableImg.onload = updateScale;
window.addEventListener('resize', updateScale);
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

// --- Palette drag ---
document.querySelectorAll('.palette-ball').forEach(img => {
  img.addEventListener('dragstart', (e) => {
    e.dataTransfer.setData('text/plain', img.dataset.ball);
    e.dataTransfer.effectAllowed = 'copy';
  });
});

// Drop on table
container.addEventListener('dragover', (e) => {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'copy';
});

container.addEventListener('drop', (e) => {
  e.preventDefault();
  const ballNum = parseInt(e.dataTransfer.getData('text/plain'));
  if (isNaN(ballNum)) return;
  const rect = tableImg.getBoundingClientRect();
  const dispX = e.clientX - rect.left;
  const dispY = e.clientY - rect.top;
  let [tx, ty] = clampToTable(...pxToTable(dispX, dispY));
  [tx, ty] = resolveOverlaps(ballNum, tx, ty);
  placeBall(ballNum, tx, ty);
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

  // Click to select
  el.addEventListener('mousedown', (e) => {
    // Will be handled by the drag system
  });
  el.addEventListener('click', (e) => {
    e.stopPropagation();
    selectBall(num);
  });

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
  // Deselect previous
  if (selectedBall !== null && placedBalls[selectedBall]) {
    placedBalls[selectedBall].el.classList.remove('selected');
  }
  selectedBall = num;
  if (placedBalls[num]) {
    placedBalls[num].el.classList.add('selected');
  }
}

function deselectAll() {
  if (selectedBall !== null && placedBalls[selectedBall]) {
    placedBalls[selectedBall].el.classList.remove('selected');
  }
  selectedBall = null;
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

// Table dragging
function makeTableDraggable(el, entry) {
  let dragging = false;
  let startX, startY, origLeft, origTop;
  let moved = false;

  el.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    dragging = true;
    moved = false;
    startX = e.clientX;
    startY = e.clientY;
    origLeft = parseFloat(el.style.left) || 0;
    origTop = parseFloat(el.style.top) || 0;
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
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

  document.addEventListener('mouseup', () => {
    if (dragging) {
      dragging = false;
      if (moved) exportCLI();
    }
  });
}

// Keyboard
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    deselectAll();
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedBall !== null) {
    removeBall(selectedBall);
  }
});

// Click on table background to deselect
container.addEventListener('click', (e) => {
  if (e.target === tableImg) {
    deselectAll();
  }
});

// Mouse coords
container.addEventListener('mousemove', (e) => {
  const rect = tableImg.getBoundingClientRect();
  const [tx, ty] = pxToTable(e.clientX - rect.left, e.clientY - rect.top);
  if (selectedBall === null) {
    coordsEl.textContent = `(${tx}, ${ty})`;
  }
});

// Export CLI
function exportCLI() {
  const nums = Object.keys(placedBalls).map(Number).sort((a, b) => a - b);
  if (nums.length === 0) {
    output.textContent = 'No balls placed.';
    return;
  }
  const parts = ['python -m pooltool.cli --ppi 24'];
  nums.forEach(n => {
    const b = placedBalls[n];
    parts.push(`-b ${n}:${b.tx},${b.ty}`);
  });
  output.textContent = parts.join(' \\\n  ');
}

// Reposition on resize
window.addEventListener('resize', () => {
  updateScale();
  Object.values(placedBalls).forEach(positionBall);
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
