(function () {
  const data = window.__BASEBALL_DATA__;
  const fps = data.fps;

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111111);

  // z-up matches simulation coordinates where z is height
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.01, 200);
  camera.up.set(0, 0, 1);
  camera.position.set(0, -8, 3);

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 10, 1.5);
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

  function buildStrikeZone(sz) {
    const { halfWidth: w, bottom: bot, top } = sz;
    const corners = [
      new THREE.Vector3(-w, 0, bot),
      new THREE.Vector3(-w, 0, top),
      new THREE.Vector3( w, 0, top),
      new THREE.Vector3( w, 0, bot),
    ];
    const outline = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints([...corners, corners[0]]),
      new THREE.LineBasicMaterial({ color: 0x4488ff })
    );
    scene.add(outline);

    const fillGeo = new THREE.BufferGeometry();
    fillGeo.setAttribute('position', new THREE.Float32BufferAttribute([
      -w, 0, bot,   w, 0, bot,   w, 0, top,
      -w, 0, bot,   w, 0, top,  -w, 0, top,
    ], 3));
    const fill = new THREE.Mesh(fillGeo, new THREE.MeshBasicMaterial({
      color: 0x4488ff, opacity: 0.1, transparent: true, side: THREE.DoubleSide,
    }));
    scene.add(fill);

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
    const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ vertexColors: true }));
    scene.add(line);
    return line;
  }

  function buildCrossingCircle(crossing, r) {
    if (!crossing) return null;
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const a = (i / 64) * Math.PI * 2;
      pts.push(new THREE.Vector3(crossing.x + r * Math.cos(a), 0, crossing.z + r * Math.sin(a)));
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

    // Circles centered at origin; repositioning the group each frame avoids geometry rebuilds
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

  // Build scene objects, collecting references for the legend
  const strikeZoneObjects = buildStrikeZone(data.strikeZone);
  const trajectoryLines   = data.trajectories.map(traj => buildTrajectoryLine(traj));
  const crossingCircles   = data.crossings.map(c => buildCrossingCircle(c, data.baseballRadius));
  const balls = data.trajectories.map(traj => {
    const group = buildBall(data.baseballRadius);
    const last = traj.frames[traj.frames.length - 1];
    group.position.set(last[0], last[1], last[2]);
    return group;
  });

  // Legend
  function buildLegend(items) {
    const panel = document.createElement('div');
    panel.style.cssText = [
      'position:fixed', 'top:20px', 'right:20px',
      'background:rgba(0,0,0,0.65)', 'padding:12px 16px', 'border-radius:8px',
      'font-family:monospace', 'color:#eee', 'min-width:140px', 'user-select:none',
    ].join(';');
    document.body.appendChild(panel);

    items.forEach(({ label, color, objects }) => {
      const row = document.createElement('div');
      row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:4px 0;cursor:pointer;';

      const swatch = document.createElement('div');
      swatch.style.cssText = `width:10px;height:10px;border-radius:2px;background:${color};flex-shrink:0;`;

      const text = document.createElement('span');
      text.textContent = label;

      let visible = true;
      row.addEventListener('click', () => {
        visible = !visible;
        objects.forEach(o => { if (o) o.visible = visible; });
        row.style.opacity = visible ? '1' : '0.35';
        text.style.textDecoration = visible ? '' : 'line-through';
      });

      row.appendChild(swatch);
      row.appendChild(text);
      panel.appendChild(row);
    });
  }

  const legendItems = [
    { label: 'Strike Zone', color: '#4488ff', objects: strikeZoneObjects },
  ];
  data.trajectories.forEach((traj, i) => {
    legendItems.push({
      label: traj.label,
      color: '#' + plasmaColor(0.5).getHexString(),
      objects: [trajectoryLines[i], balls[i]],
    });
  });
  data.crossings.forEach((c, i) => {
    if (crossingCircles[i]) {
      const label = data.trajectories.length > 1
        ? 'Crossing: ' + data.trajectories[i].label
        : 'Crossing Point';
      legendItems.push({ label, color: '#ff4444', objects: [crossingCircles[i]] });
    }
  });
  buildLegend(legendItems);

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
  slider.value = maxFrames - 1;
  slider.style.cssText = 'width:260px;cursor:pointer;';
  ui.appendChild(slider);

  const timeLabel = document.createElement('span');
  timeLabel.style.width = '90px';
  ui.appendChild(timeLabel);

  playBtn.addEventListener('click', () => {
    if (playing) {
      playing = false;
      playBtn.textContent = 'Play';
    } else {
      if (frameIndex >= maxFrames - 1) setFrame(0);
      startTime = performance.now() - (frameIndex / fps) * 1000;
      playing = true;
      playBtn.textContent = 'Pause';
    }
  });

  slider.addEventListener('input', () => {
    playing = false;
    playBtn.textContent = 'Play';
    setFrame(parseInt(slider.value));
  });

  setFrame(maxFrames - 1);

  function animate(ts) {
    requestAnimationFrame(animate);
    if (playing) {
      const i = Math.floor((ts - startTime) / 1000 * fps);
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
