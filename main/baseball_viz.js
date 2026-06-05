// TO-DO: fix bugs with infield color overlap

(function () {
  const data = window.__BASEBALL_DATA__;
  const fps = data.fps;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111111);

  // z-up matches simulation coordinates where z is height
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.01, 200);
  camera.up.set(0, 0, 1);
  camera.position.set(0, -2, 0.8);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 18.44, 1.8);
  controls.update();

  // Sampled from matplotlib's Plasma colormap at t = 0, 0.25, 0.5, 0.75, 1.0
  const PLASMA = [
    [0.050383, 0.029803, 0.527975],
    [0.494877, 0.011990, 0.657865],
    [0.798216, 0.280197, 0.469538],
    [0.972303, 0.585743, 0.220860],
    [0.940015, 0.975158, 0.131326],
  ];

  function plasmaColor(t) {
    const s = Math.max(0, Math.min(1, t)) * (PLASMA.length - 1);
    const i = Math.min(Math.floor(s), PLASMA.length - 2);
    const f = s - i;
    const a = PLASMA[i], b = PLASMA[i + 1];
    return new THREE.Color(
      a[0] + f * (b[0] - a[0]),
      a[1] + f * (b[1] - a[1]),
      a[2] + f * (b[2] - a[2])
    );
  }

  function buildStrikeZone(sz, plateY) {
    const { halfWidth: w, bottom: bot, top } = sz;
    const p = plateY;
    const corners = [
      new THREE.Vector3(-w, p, bot),
      new THREE.Vector3(-w, p, top),
      new THREE.Vector3( w, p, top),
      new THREE.Vector3( w, p, bot),
    ];
    const outline = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([...corners, corners[0]]),
      new THREE.LineBasicMaterial({ color: 0x4488ff })
    );
    scene.add(outline);

    const fillGeo = new THREE.BufferGeometry();
    fillGeo.setAttribute('position', new THREE.Float32BufferAttribute([
      -w, p, bot,   w, p, bot,   w, p, top,
      -w, p, bot,   w, p, top,  -w, p, top,
    ], 3));
    const fill = new THREE.Mesh(fillGeo, new THREE.MeshBasicMaterial({
      color: 0x4488ff, opacity: 0.1, transparent: true, side: THREE.DoubleSide,
    }));
    //scene.add(fill);

    return [outline, fill];
  }

  function buildTrajectoryLine(traj) {
    const pos = [], col = [];
    for (let i = 0; i < traj.x.length; i++) {
      pos.push(traj.x[i], traj.y[i], traj.z[i]);
      const c = plasmaColor(traj.t_norm[i]);
      col.push(c.r, c.g, c.b);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    geo.setAttribute('color',    new THREE.Float32BufferAttribute(col, 3));
    geo.setDrawRange(0, 0);
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ vertexColors: true }));
    scene.add(line);
    return { line, geo };
  }

  function buildCrossingCircle(crossing, r) {
    if (!crossing) return null;
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(crossing.x + r * Math.cos(a), crossing.y, crossing.z + r * Math.sin(a)));
    }
    const circle = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0xff2222 })
    );
    scene.add(circle);
    return circle;
  }

  function buildBall(r) {
    const mat = new THREE.LineBasicMaterial({ color: 0xffffff });
    const group = new THREE.Group();
    const circlePoints = (axisFn) => {
      const pts = [];
      for (let i = 0; i <= 64; i++) {
        const a = (i / 64) * Math.PI * 2;
        pts.push(axisFn(Math.cos(a) * r, Math.sin(a) * r));
      }
      return pts;
    };

    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
      circlePoints((c, s) => new THREE.Vector3(c, s, 0))  // XY plane
    ), mat));
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
      circlePoints((c, s) => new THREE.Vector3(c, 0, s))  // XZ plane
    ), mat));
    group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
      circlePoints((c, s) => new THREE.Vector3(0, c, s))  // YZ plane
    ), mat));

    scene.add(group);
    return group;
  }

  function buildField(plateY) {
    const BASE_DIST   = 27.432;   // 90 ft
    const MOUND_DIST  = 18.4404;  // 60.5 ft
    const INFIELD_R   = 28.956;   // 95 ft — covers basepaths
    const OF_RADIUS   = 109.728;  // 360 ft
    const MOUND_R     = 2.7432;   // 9 ft
    const PATH_HW     = 0.5334;   // ~21 in, slightly wider than the plate
    const FOUL_ANGLE  = Math.PI / 4;

    const GRASS_OPACITY = 0.30;
    const DIRT_OPACITY  = 0.20;
    const GRASS_COLOR   = 0x1a6b1a;
    const DIRT_COLOR    = 0x7a4a22;

    const s      = BASE_DIST / Math.SQRT2;  // ~19.41 m
    const moundY = plateY + MOUND_DIST;

    function filledMesh(shape, color, opacity, zLayer) {
      const mat = new THREE.MeshBasicMaterial({
        color, opacity, transparent: true, side: THREE.DoubleSide, depthWrite: false,
      });
      const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape, 64), mat);
      mesh.renderOrder = zLayer;
      mesh.position.z = zLayer * 0.001;
      scene.add(mesh);
    }

    const N = 64;

    const uI = (s + Math.sqrt(2 * INFIELD_R * INFIELD_R - s * s)) / 2;  // foul-line / circle intersection dist
    const rightAngle = Math.atan2(uI - s, uI);
    const leftAngle  = Math.PI - rightAngle;

    const grassShape = new THREE.Shape();
    grassShape.moveTo(0, plateY);
    for (let i = 0; i <= N; i++) {
      const a = -FOUL_ANGLE + (2 * FOUL_ANGLE * i / N);
      grassShape.lineTo(Math.sin(a) * OF_RADIUS, plateY + Math.cos(a) * OF_RADIUS);
    }
    grassShape.closePath();

    const infieldHole = new THREE.Path();
    infieldHole.moveTo(0, plateY);
    infieldHole.lineTo(uI, plateY + uI);                                         // right foul line to circle
    infieldHole.absarc(0, plateY + s, INFIELD_R, rightAngle, leftAngle, false);  // CCW arc over top
    infieldHole.lineTo(0, plateY);                                                // left foul line back to home
    grassShape.holes.push(infieldHole);
    filledMesh(grassShape, GRASS_COLOR, GRASS_OPACITY, 1);

    // Infield dirt circle 
    const dirtShape = new THREE.Shape();
    dirtShape.absarc(0, plateY + s, INFIELD_R, 0, Math.PI * 2, false);
    filledMesh(dirtShape, DIRT_COLOR, DIRT_OPACITY, 2);

    // Pitcher's mound 
    const moundShape = new THREE.Shape();
    moundShape.absarc(0, moundY, MOUND_R, 0, Math.PI * 2, false);
    filledMesh(moundShape, DIRT_COLOR, DIRT_OPACITY, 3);
  }

  // Build scene objects, collecting references for the legend
  buildField(data.plateY);
  const strikeZoneObjects = buildStrikeZone(data.strikeZone, data.plateY);
  const trajectoryBuilt = data.trajectories.map(traj => buildTrajectoryLine(traj));
  const trajectoryLines = trajectoryBuilt.map(d => d.line);
  const trajectoryGeos  = trajectoryBuilt.map(d => d.geo);
  const crossingCircles   = data.crossings.map(c => buildCrossingCircle(c, data.baseballRadius));
  const balls = data.trajectories.map(traj => {
    const group = buildBall(data.baseballRadius);
    const first = traj.frames[0];
    group.position.set(first[0], first[1], first[2]);
    return group;
  });

  function buildMagnusArrow() {
    const arrow = new THREE.ArrowHelper(
      new THREE.Vector3(0, 1, 0),  // placeholder direction
      new THREE.Vector3(0, 0, 0),  // placeholder origin
      0.2, 0x00ff88, 0.04, 0.02
    );
    scene.add(arrow);
    return arrow;
  }
  const magnusArrows = data.trajectories.map(traj => {
    if (!traj.magnusDirections) return null;
    const arrow = buildMagnusArrow();
    arrow.visible = false;
    return arrow;
  });

  // Legend
  // Per-trajectory and global visibility state; effective visibility = traj AND global.
  const trajVisible = data.trajectories.map(() => true);
  const globalTracesOn    = { value: true };
  const globalBallsOn     = { value: true };
  const globalCrossingsOn = { value: true };
  const globalMagnusOn    = { value: false };

  function applyTrace(i) {
    trajectoryLines[i].visible = trajVisible[i] && globalTracesOn.value;
  }
  function applyBall(i) {
    balls[i].visible = trajVisible[i] && globalBallsOn.value;
  }
  function applyCrossing(i) {
    if (crossingCircles[i]) crossingCircles[i].visible = trajVisible[i] && globalCrossingsOn.value;
  }
  function applyMagnus(i) {
    if (magnusArrows[i]) magnusArrows[i].visible = trajVisible[i] && globalMagnusOn.value;
  }

  function makeToggleRow(label, color, onClick, initialVisible = true) {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;';

    const swatch = document.createElement('div');
    swatch.style.cssText = `width:10px;height:10px;border-radius:2px;background:${color};flex-shrink:0;`;

    const text = document.createElement('span');
    text.textContent = label;

    let visible = initialVisible;
    row.style.opacity = visible ? '1' : '0.35';
    text.style.textDecoration = visible ? '' : 'line-through';
    const setVisible = (v) => {
      if (v === visible) return;
      visible = v;
      onClick(visible);
      row.style.opacity = visible ? '1' : '0.35';
      text.style.textDecoration = visible ? '' : 'line-through';
    };
    row.addEventListener('click', () => setVisible(!visible));

    row.appendChild(swatch);
    row.appendChild(text);
    return { row, setVisible };
  }

  function buildLegend() {
    const panel = document.createElement('div');
    panel.style.cssText = [
      'position:fixed', 'top:20px', 'right:20px',
      'background:rgba(0,0,0,0.65)', 'padding:12px 16px', 'border-radius:8px',
      'font-family:monospace', 'color:#eee', 'min-width:140px', 'user-select:none',
    ].join(';');
    document.body.appendChild(panel);

    // Strike zone
    panel.appendChild(makeToggleRow('Strike Zone', '#4488ff', visible => {
      strikeZoneObjects.forEach(o => { o.visible = visible; });
    }).row);

    // Trajectory section header
    const trajHeader = document.createElement('div');
    trajHeader.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:4px 0 2px;';

    const selectBtn = document.createElement('button');
    selectBtn.textContent = 'Deselect All';
    selectBtn.style.cssText = 'padding:1px 6px;border:1px solid #555;background:#1a1a1a;color:#aaa;border-radius:3px;cursor:pointer;font-family:monospace;font-size:0.75em;';

    trajHeader.appendChild(selectBtn);
    panel.appendChild(trajHeader);

    // Per-trajectory rows
    const trajSetVisible = [];
    data.trajectories.forEach((traj, i) => {
      const color = '#' + plasmaColor(0.5).getHexString();
      const { row, setVisible } = makeToggleRow(traj.label, color, visible => {
        trajVisible[i] = visible;
        applyTrace(i);
        applyBall(i);
        applyCrossing(i);
        applyMagnus(i);
      });
      trajSetVisible.push(setVisible);
      panel.appendChild(row);
    });

    selectBtn.addEventListener('click', () => {
      const allOn = trajSetVisible.every((_, i) => trajVisible[i]);
      trajSetVisible.forEach((set, i) => set(!allOn));
      selectBtn.textContent = allOn ? 'Select All' : 'Deselect All';
    });

    // Global toggles
    const sep = document.createElement('div');
    sep.style.cssText = 'border-top:1px solid #444;margin:6px 0;';
    panel.appendChild(sep);

    panel.appendChild(makeToggleRow('Traces', '#aaaaaa', visible => {
      globalTracesOn.value = visible;
      data.trajectories.forEach((_, i) => applyTrace(i));
    }).row);
    panel.appendChild(makeToggleRow('Balls', '#ffffff', visible => {
      globalBallsOn.value = visible;
      data.trajectories.forEach((_, i) => applyBall(i));
    }).row);

    const hasCrossings = crossingCircles.some(Boolean);
    const hasMagnus    = magnusArrows.some(Boolean);

    if (hasCrossings) {
      panel.appendChild(makeToggleRow('Crossings', '#ff4444', visible => {
        globalCrossingsOn.value = visible;
        data.trajectories.forEach((_, i) => applyCrossing(i));
      }).row);
    }
    if (hasMagnus) {
      panel.appendChild(makeToggleRow('Magnus Dir', '#00ff88', visible => {
        globalMagnusOn.value = visible;
        data.trajectories.forEach((_, i) => applyMagnus(i));
      }, false).row);
    }
  }

  buildLegend();

  // Animation state
  let playing = false;
  let frameIndex = 0;
  let startTime = null;
  const maxFrames = Math.max(...data.trajectories.map(t => t.frames.length));

  function setFrame(i) {
    frameIndex = Math.max(0, Math.min(i, maxFrames - 1));
    data.trajectories.forEach((traj, ti) => {
      const f = traj.frames[Math.min(frameIndex, traj.frames.length - 1)];
      balls[ti].position.set(f[0], f[1], f[2]);
      const drawCount = frameIndex === 0 ? 0 : Math.min(frameIndex + 1, traj.x.length);
      trajectoryGeos[ti].setDrawRange(0, drawCount);
      if (magnusArrows[ti] && traj.magnusDirections) {
        const dir = traj.magnusDirections[Math.min(frameIndex, traj.magnusDirections.length - 1)];
        const p = balls[ti].position;
        magnusArrows[ti].position.set(p.x, p.y, p.z);
        magnusArrows[ti].setDirection(new THREE.Vector3(dir[0], dir[1], dir[2]).normalize());
      }
    });
    slider.value = frameIndex;
    timeLabel.textContent = 't = ' + (frameIndex / fps).toFixed(3) + ' s';
  }

  const ui = document.createElement('div');
  ui.style.cssText = [
    'position:fixed', 'bottom:20px', 'left:50%', 'transform:translateX(-50%)',
    'display:flex', 'align-items:center', 'gap:12px',
    'background:rgba(0,0,0,0.65)', 'padding:10px 18px', 'border-radius:8px',
    'font-family:monospace', 'color:#eee',
  ].join(';');
  document.body.appendChild(ui);

  const playBtn = document.createElement('button');
  playBtn.textContent = 'Play';
  playBtn.style.cssText = 'padding:4px 14px;border:1px solid #666;background:#222;color:#eee;border-radius:4px;cursor:pointer;font-family:monospace;';
  ui.appendChild(playBtn);

  const slider = document.createElement('input');
  slider.type = 'range';
  slider.min = 0;
  slider.max = maxFrames - 1;
  slider.value = 0;
  slider.style.cssText = 'width:260px;cursor:pointer;';
  ui.appendChild(slider);

  const timeLabel = document.createElement('span');
  timeLabel.style.width = '90px';
  ui.appendChild(timeLabel);

  const speedSelect = document.createElement('select');
  speedSelect.style.cssText = 'padding:4px 6px;border:1px solid #666;background:#222;color:#eee;border-radius:4px;cursor:pointer;font-family:monospace;';
  [['1x', 1], ['0.75x', 0.75], ['0.5x', 0.5], ['0.25x', 0.25]].forEach(([label, val]) => {
    const opt = document.createElement('option');
    opt.value = val;
    opt.textContent = label;
    speedSelect.appendChild(opt);
  });
  ui.insertBefore(speedSelect, slider);

  let speed = 1;
  speedSelect.addEventListener('change', () => {
    const wasPlaying = playing;
    if (wasPlaying) {
      playing = false;
    }
    speed = parseFloat(speedSelect.value);
    if (wasPlaying) {
      startTime = performance.now() - (frameIndex / fps / speed) * 1000;
      playing = true;
    }
  });

  playBtn.addEventListener('click', () => {
    if (playing) {
      playing = false;
      playBtn.textContent = 'Play';
    } else {
      if (frameIndex >= maxFrames - 1) setFrame(0);
      startTime = performance.now() - (frameIndex / fps / speed) * 1000;
      playing = true;
      playBtn.textContent = 'Pause';
    }
  });

  slider.addEventListener('input', () => {
    playing = false;
    playBtn.textContent = 'Play';
    setFrame(parseInt(slider.value));
  });

  setFrame(0);

  function animate(ts) {
    requestAnimationFrame(animate);
    if (playing) {
      const i = Math.floor((ts - startTime) / 1000 * fps * speed);
      if (i >= maxFrames) {
        playing = false;
        playBtn.textContent = 'Play';
        setFrame(maxFrames - 1);
      } else {
        setFrame(i);
      }
    }
    controls.update();
    renderer.render(scene, camera);
  }
  requestAnimationFrame(animate);

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });
})();
