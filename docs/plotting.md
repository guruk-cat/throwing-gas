# Plotting

## Dependencies

**Python:** `plotly`, `numpy`, `yaml` (all in static and animated modes).

**Animated mode only:** the generated HTML loads Three.js r134 and OrbitControls from CDN at browser open time. An internet connection is required on first load.

## Python-end compute

`Trajectory3DPlot` in `src/Plotter.py` handles two modes, selected by the `animate` flag passed to `plot()`. For convenience during testing, `launch.py` defaults its `--plot` argument to `animate`.

**Static mode** builds a Plotly `Figure` directly and calls `.show()` 

**Animated mode** writes a self-contained HTML file and opens it in the browser:
- Trajectories are resampled to a uniform time grid at the target `fps` using `numpy.interp`. The final simulation timestamp is always included explicitly so the ball reaches the plate rather than stopping one frame short.
- Per-trajectory metadata (full path for color mapping, resampled frames for animation, plate-crossing coordinates) is serialized as a JSON blob into `window.__BASEBALL_DATA__` in the HTML.
- `src/baseball_viz.js` is read from disk at runtime and injected inline — no build step required.

**Crossing point interpolation** (`_crossing_point`): finds the last index where `y >= 0`, then linearly interpolates between that point and the next to find the exact `x, z` position at `y = 0`. Returns `None` if the ball never reaches the plate.

## JS and CSS

`src/baseball_viz.js` is a self-contained IIFE that reads `window.__BASEBALL_DATA__` and builds a Three.js scene.

**Three.js instead of Plotly animation:** Plotly's 3D animation requires `redraw=True` on every frame, which forces a full WebGL scene reconstruction (~33ms/frame). This caps animation at ~30fps regardless of frame rate settings. Three.js updates only the ball's transform each frame (`group.position.set(x, y, z)`) — an O(1) operation — which is why 60fps is achievable.

**Coordinate system:** the simulation uses z-up (z = height, y = distance from pitcher to plate). Three.js defaults to y-up. Rather than remapping coordinates, `camera.up` is set to `(0, 0, 1)` so Three.js treats z as the vertical axis — no coordinate transforms needed anywhere.

**Plasma colormap:** five control points sampled from matplotlib's Plasma at `t = 0, 0.25, 0.5, 0.75, 1.0` are hardcoded in JS and linearly interpolated, removing any matplotlib dependency from the browser.

**Scene background** is set via `scene.background` in Three.js. The `<body>` CSS has no background color because the canvas fills the full viewport.
