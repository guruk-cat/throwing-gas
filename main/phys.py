import re
import types
import pint
import numpy
from numpy.linalg import norm



ureg = pint.UnitRegistry()
ureg.define('percent = 0.01 rad')   # convenience unit for relative error tolerances
Q_ = ureg.Quantity                  # type: ignore[misc]
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

# Pitcher body proportion constants; used when precise values are not provided
_K_SH           = 0.63    # shoulder height as fraction of pitcher height during delivery (absorbs knee bend + forward lean)
_K_ARM          = 0.37    # arm length as fraction of pitcher height
_K_EXT          = 0.082   # arm extension (forward lean) as fraction of pitcher height (~15 cm for 182 cm pitcher)
_K_STRIDE       = 0.85    # shoulder stride toward plate as fraction of pitcher height (back-computed from Statcast avg ~5.75 ft extension)
_MOUND_HEIGHT_M = 0.254   # standard mound height above field level (10 in)

# Quick-acess defaults; only for convenience
DEFAULT_TIME_STEP = Q_(0.5, 'ms')
DEFAULT_MAGNUS_COEFFICIENT = Q_(1.37800775e-06, 'kg * s / m')
DEFAULT_DRAG_COEFFICIENT = Q_(6.30816026e-04, 'kg/m')
DEFAULT_MAGNUS_MODEL = 'squared velocity'

# Air density
_R_DRY   = 287.0500676   # specific gas constant of dry air      [J/(kg·K)]
_R_VAPOR = 461.5         # specific gas constant of water vapor   [J/(kg·K)]

# ISA sea-level defaults
DEFAULT_TEMPERATURE = Q_(15, 'degC')
DEFAULT_PRESSURE    = Q_(1013.25, 'hPa')
DEFAULT_HUMIDITY    = Q_(0, 'percent')



# Helper functions

def rot_x(theta):
  t = theta.to('radian').magnitude
  return numpy.array([[1, 0,            0           ],
                      [0, numpy.cos(t), -numpy.sin(t)],
                      [0, numpy.sin(t),  numpy.cos(t)]])

def rot_y(theta):
  t = theta.to('radian').magnitude
  return numpy.array([[ numpy.cos(t), 0, numpy.sin(t)],
                      [ 0,            1, 0           ],
                      [-numpy.sin(t), 0, numpy.cos(t)]])

def rot_z(theta):
  t = theta.to('radian').magnitude
  return numpy.array([[numpy.cos(t), -numpy.sin(t), 0],
                      [numpy.sin(t),  numpy.cos(t), 0],
                      [0,             0,            1]])

def rot_axis(axis, theta):
  # Rodrigues rotation matrix: angle theta around arbitrary axis.
  k = numpy.asarray(axis, dtype=float)
  k = k / norm(k)
  t = theta.to('radian').magnitude
  K = numpy.array([[    0, -k[2],  k[1]],   # skew-symmetric cross-product matrix for k
                   [ k[2],     0, -k[0]],
                   [-k[1],  k[0],     0]])
  return numpy.cos(t)*numpy.eye(3) + numpy.sin(t)*K + (1 - numpy.cos(t))*numpy.outer(k, k)

def si_mag(q):
  # Strip pint quantity to its SI base-unit magnitude.
  return q.to_base_units().magnitude

def parse_quantity(s):
  # Handle "X ft Y in" compound format not natively supported by pint.
  # Plain numbers default to metres.
  if isinstance(s, (int, float)):
    return Q_(float(s), 'm')
  m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*ft\s+(\d+(?:\.\d+)?)\s*in\s*$', s)
  if m:
    return Q_(float(m.group(1)) * 12 + float(m.group(2)), 'in')
  return Q_(s)

def parse_scene(scene):
  '''
  Parse a `scene` block into (temperature, pressure, humidity) quantities,
  defaulting any omitted key to its sea-level value. Values are split into
  magnitude + unit explicitly because the generic Q_(s) multiply path chokes
  on offset units like degC.
  '''
  out = {'temperature': DEFAULT_TEMPERATURE,
         'pressure':    DEFAULT_PRESSURE,
         'humidity':    DEFAULT_HUMIDITY}
  for key in out:
    if key in scene:
      m = re.match(r'^\s*(-?\d+(?:\.\d+)?)\s*(.*\S)\s*$', str(scene[key]))
      out[key] = Q_(float(m.group(1)), m.group(2))
  return out['temperature'], out['pressure'], out['humidity']

def air_density(temperature, pressure, humidity):
  '''
  Humid-air density (Q_ in kg/m^3), treating the air as an ideal-gas mixture
  of dry air and water vapor:  rho = P_d / (R_d * T) + P_v / (R_v * T).
  Saturation vapor pressure uses the Tetens approximation (over water).
  See https://en.wikipedia.org/wiki/Density_of_air#Humid_air
  '''
  T_C = temperature.to('degC').magnitude
  T_K = temperature.to('kelvin').magnitude
  P   = pressure.to('Pa').magnitude
  RH  = humidity.to('dimensionless').magnitude        # fraction of saturation

  P_sat = 610.78 * 10 ** (7.5 * T_C / (T_C + 237.3))  # Tetens, Pa
  P_v   = RH * P_sat                                  # water-vapor partial pressure
  P_d   = P - P_v                                     # dry-air partial pressure

  rho = P_d / (_R_DRY * T_K) + P_v / (_R_VAPOR * T_K)
  return Q_(rho, 'kg/m**3')



# Frame builders

def arm_direction(arm_slot_rad, handedness, arm_extension_m=0.0, arm_length_m=1.0):
  # Unit vector from shoulder to hand at release, in world coordinates.
  # Righty arm is on world -x side (pitcher's right); lefty on +x.
  sign  = -1.0 if handedness.lower().startswith('r') else 1.0
  e     = arm_extension_m / arm_length_m    # normalised forward lean ∈ [0, 1)
  scale = numpy.sqrt(1.0 - e**2)            # lateral/vertical amplitude shrinks as arm leans forward
  v = numpy.array([sign * numpy.cos(arm_slot_rad) * scale,
                   -e,
                   numpy.sin(arm_slot_rad) * scale])
  return v / norm(v)

def build_pitch_frame(release_world, arm_dir):
  '''
  Build the pitch-to-world rotation matrix M (v_world = M @ v_pitch).
  y_pitch: unit vector from home plate toward release point.
  x_pitch: normal to the plane of y_pitch and arm (pure backspin/topspin axis).
  z_pitch: right-hand completion — points roughly up.
  Raises ValueError if arm_dir is parallel to y_pitch (degenerate frame).
  '''
  y_pitch = release_world / norm(release_world)
  cross   = numpy.cross(y_pitch, arm_dir)
  if norm(cross) < 1e-6:
    raise ValueError("arm_dir is parallel to y_pitch — pitch frame is degenerate (arm pointing straight at plate).")
  x_pitch = cross / norm(cross)
  z_pitch = numpy.cross(x_pitch, y_pitch)
  return numpy.column_stack([x_pitch, y_pitch, z_pitch])


'''
Force terms

* Each returns an acceleration contribution (m/s^2) given a state vector and a
constants bundle `c`. 
* Both Simulation.derivative() and Configuration.velo_correction() go through 
acceleration(), and plotting derives the Magnus vector via magnus_acc().
'''

def gravity_acc(state, c):
  return -c.g * zhat

def drag_acc(state, c):
  v = state[4:7]
  return -(c.Cd * c.rho / c.m) * norm(v) * v

def magnus_acc(state, c):
  v = state[4:7]
  cross = numpy.cross(state[7:10], v)
  if c.magnus_model == 'squared velocity':
    return (c.Cm * c.rho / c.m) * norm(v) * cross
  elif c.magnus_model == 'linear velocity':
    return (c.Cm * c.rho / c.m) * cross
  raise Exception(f"Unrecognized magnus model '{c.magnus_model}'")

ALL_TERMS = (gravity_acc, drag_acc, magnus_acc)

def acceleration(state, c, terms=None):
  # Sum the enabled force terms. Order matches the historical gravity, drag,
  # magnus accumulation so results are bit-identical.
  if terms is None:
    terms = getattr(c, 'enabled_terms', None) or ALL_TERMS
  total = numpy.zeros(3)
  for term in terms:
    total = total + term(state, c)
  return total



class Simulation:

  @property
  def state_size(self):
    '''
    state vector layout:
    [0]    t
    [1:4]  x, y, z     (m)
    [4:7]  vx, vy, vz  (m/s)
    [7:10] wx, wy, wz  (rad/s)
    '''
    return 10

  def derivative(self, state, c):
    dsdt = numpy.zeros(self.state_size)
    dsdt[0]   = 1                        # dt/dt = 1
    dsdt[1:4] = state[4:7]               # dx/dt = v
    dsdt[4:7] = acceleration(state, c)   # dv/dt = (Fg + Fd + Fm) / m
    # dw/dt = 0 (spin treated as constant for now)
    return dsdt

  def rk4(self, time_step, state, c):
    k1 = time_step * self.derivative(state, c)
    k2 = time_step * self.derivative(state + k1 / 2, c)
    k3 = time_step * self.derivative(state + k2 / 2, c)
    k4 = time_step * self.derivative(state + k3, c)
    return state + (k1 + 2*k2 + 2*k3 + k4) / 6

  def modified_rk4(self, time_step, state, c):
    # returns point acceleration
    d1 = self.derivative(state, c)
    k1 = time_step * d1
    d2 = self.derivative(state + k1 / 2, c)
    k2 = time_step * d2
    d3 = self.derivative(state + k2/2, c)
    k3 = time_step * d3
    d4 = self.derivative(state + k3, c)
    return (d1 + 2*d2 + 2*d3 + d4) / 6

  def _step_error(self, s0, s1, s2):
    # relative error: how much the double-half-step s2 differs from the full-step s1,
    # normalised by the total displacement from s0
    return norm(s2 - s1) / norm(s2 - s0)

  def point_run(self, launch_config, print_debug=False):
    # compute derivative of velo vector for one time step and return vector
    c = launch_config.constants()
    state = numpy.zeros(self.state_size)
    state[4:7]  = launch_config.get_velocity(suppress_velo_correction=True)
    state[7:10] = launch_config.get_spin()

    dt = c.dt
    s_half_step = self.rk4(dt/2, state, c)  # for matching regular run() precision
    ds_dt = self.modified_rk4(dt/2, s_half_step, c)
    dv_dt = ds_dt[4:7]

    if print_debug:
      print(f"time      : {state[0]}")
      print(f"init pos  : [{', '.join(str(v) for v in state[1:4])}]")
      print(f"init velo : [{', '.join(str(v) for v in state[4:7])}]")
      print(f"init spin : [{', '.join(str(v) for v in state[7:10])}]")
      print(f"dt        : {dt}")
      print(f"dv_dt     : [{', '.join(str(v) for v in dv_dt)}]\n")

    return dv_dt

  def run(self, launch_config, terminate_function=lambda record: len(record) > 1000, record_all=True, adaptive=True):
    c = launch_config.constants()
    state = numpy.zeros(self.state_size)
    state[1:4]  = launch_config.get_position()
    state[4:7]  = launch_config.get_velocity()
    state[7:10] = launch_config.get_spin()

    record = [state.copy()]
    dt = c.dt
    if not adaptive:
      dt = dt/2   # exists to match the precision of adaptive stepping's dt/2

    while not terminate_function(record):
      # adaptive step: compare one full step vs two half steps;
      # halve dt if error too large
      while adaptive:
        s1  = self.rk4(dt, state, c)
        s2  = self.rk4(dt/2, self.rk4(dt/2, state, c), c)
        err = self._step_error(state, s1, s2)
        if c.auto_converge and err > c.tol:
          print(f"Info: decreasing time step from {dt} to {dt/2}")
          dt /= 2
        else:
          state = s2  # use the better one since it's already computed anyways
          break

      if adaptive:
        dt *= c.growth

      if not adaptive:
        state = self.rk4(dt, state, c)

      if record_all:
        record.append(state.copy())
      else:
        record[0] = state.copy()

    return record


class Configuration:
  def __init__(self):
    # Scene / environment parameters (used to compute air density)
    self.temperature = DEFAULT_TEMPERATURE   # Q_ temperature
    self.pressure    = DEFAULT_PRESSURE      # Q_ pressure
    self.humidity    = DEFAULT_HUMIDITY      # Q_ relative humidity (fraction of saturation)

    # Physics constants and integration knobs
    # These feed both the forward sim and velo_correction.
    self.drag_coefficient           = DEFAULT_DRAG_COEFFICIENT
    self.magnus_coefficient         = DEFAULT_MAGNUS_COEFFICIENT
    self.ball_mass                  = Q_(145, 'g')
    self.ball_diameter              = Q_(3, 'in')
    self.gravitational_acceleration = Q_(9.8, 'm/s**2')
    self.time_step                  = DEFAULT_TIME_STEP
    self.time_step_growth_rate      = Q_(1, '')
    self.error_tolerance            = Q_(0.1, 'percent')
    self.auto_converge_time_step    = True
    self.wind_speed                 = Q_(0, 'mph')
    self.wind_direction             = Q_(0, 'degree')
    self.enabled_terms              = None   # None -> all force terms; set to a subset for physics testing

    # Arm geometry
    self.handedness    = 'right'
    self.arm_slot      = Q_(45, 'degree')
    self.arm_extension = None              # Q_; if None, derived from height via _K_EXT
    self.arm_length    = None              # Q_; if None, derived from height via _K_ARM

    # Position
    self.release_pos   = None              # Q_ vector or ndarray (metres)
    self.height        = None              # Q_
    self.rubber        = numpy.array([0.0, 18.44])  # [x_m, y_m]

    # Velocity
    self.speed                = None       # Q_ scalar; if None, derived from velocity_vector norm
    self.aim_target           = None       # ndarray (world metres); mutually exclusive with velocity_vector
    self.velocity_vector      = None       # Q_ vector; mutually exclusive with aim_target

    # Grammar
    self.format_type = 'manual'

    # Spin
    self.spin_rate   = Q_(0, 'rad/s')
    self.spin_angle  = None                # statcast: world-frame axis tilt in the x-z plane
    self.spin_axis   = xhat.copy()         # manual: unit vector in pitch-frame coordinates
    self.clock_angle = Q_(0, 'degree')     # manual

    # Magnus model (used by the force law and velo_correction)
    self.magnus_model = DEFAULT_MAGNUS_MODEL

  def configure(self, cfg):
    fmt = cfg.get('format', {})
    config = cfg['launch']
    sim_block = cfg.get('simulation')

    # `format.type` selects the input grammar; absent defaults to manual.
    fmt_type = fmt.get('type', 'manual')
    if fmt_type not in ('statcast', 'manual'):
      raise ValueError(f"format.type must be 'statcast' or 'manual', got {fmt_type!r}.")
    self.format_type = fmt_type

    config_keys_used = []

    # keys that don't need special treatment
    for key, attr, parser in [
      ('handedness',    'handedness',    lambda v: v),
      ('magnus_model',  'magnus_model',  lambda v: v),
      ('arm_slot',      'arm_slot',      parse_quantity),
      ('arm_extension', 'arm_extension', parse_quantity),
      ('arm_length',    'arm_length',    parse_quantity),
      ('speed',         'speed',         parse_quantity),
      ('spin_rate',     'spin_rate',     parse_quantity),
    ]:
      if key in config:
        setattr(self, attr, parser(config[key]))
        config_keys_used.append(key)

    # keys that need special treatment

    if 'position' in config:
      pos = config['position']
      config_keys_used.append('position')

      if 'height' not in pos:
        raise ValueError("'position.height' is required.")
      self.height = parse_quantity(pos['height'])

      if 'release_pos' in pos:
        rp = pos['release_pos']
        self.release_pos =  numpy.array([parse_quantity(v).to('m').magnitude for v in rp])
      
      if 'rubber' in pos:
        r = pos['rubber']
        self.rubber = numpy.array([parse_quantity(r[0]).to('m').magnitude, parse_quantity(r[1]).to('m').magnitude])

    if 'velocity' in config:
      vel = config['velocity']
      config_keys_used.append('velocity')

      if 'target' in vel:
        t = vel['target']
        self.aim_target = numpy.array([parse_quantity(v).to('m').magnitude for v in t])
        self.velocity_vector = None
      elif 'vector' in vel:
        v = vel['vector']
        units = 'meter per second'
        self.velocity_vector = numpy.array([Q_(x).to(units).magnitude for x in v])
        self.aim_target = None
      else:
        raise ValueError("'velocity' must contain 'target' or 'vector'.")

    # Spin direction: keys depend on format
    if self.format_type == 'statcast':
      if 'spin_angle' not in config:
        raise ValueError("statcast format requires 'spin_angle'.")
      self.spin_angle = parse_quantity(config['spin_angle'])
      config_keys_used.append('spin_angle')
    else:
      if 'spin_axis' not in config or 'clock_angle' not in config:
        raise ValueError("manual format requires 'spin_axis' and 'clock_angle'.")
      self.spin_axis = numpy.asarray(config['spin_axis'], dtype=float)
      self.spin_axis = self.spin_axis / norm(self.spin_axis)
      self.clock_angle = parse_quantity(config['clock_angle'])
      config_keys_used.extend(['spin_axis', 'clock_angle'])

    if 'scene' in config:
      self.configure_scene(config['scene'])
      config_keys_used.append('scene')

    if len(config_keys_used) != len(config.keys()):
      print("Warning: there were unused keys when configuring LaunchConfiguration:")
      for k in list(set(config.keys()) - set(config_keys_used)):
        print("  ", k)
      print("Make sure you didn't mispell something.")

    if sim_block:
      self.configure_simulation(sim_block)

  def configure_simulation(self, block):
    # Parse the `simulation` block (physics constants and integration knobs)
    # onto this Configuration. Omitted keys keep their defaults.
    quantity_attrs = [
      'drag_coefficient', 'magnus_coefficient', 'ball_mass', 'ball_diameter',
      'gravitational_acceleration', 'time_step', 'time_step_growth_rate',
      'error_tolerance', 'wind_speed', 'wind_direction',
    ]
    for attr in quantity_attrs:
      if attr in block:
        new_val = Q_(block[attr])
        current = getattr(self, attr)
        if new_val.dimensionality != current.dimensionality:
          raise Exception(f"Configuration parameter '{attr}' has wrong dimensions. "
                          f"Expected '{current.dimensionality}' but got '{new_val.dimensionality}'.")
        setattr(self, attr, new_val)
    if 'magnus_model' in block:
      self.magnus_model = block['magnus_model']
    if 'auto_converge_time_step' in block:
      self.auto_converge_time_step = bool(block['auto_converge_time_step'])

  def configure_scene(self, scene):
    # Parse a `scene` block (temperature, pressure, humidity).
    # Any omitted key keeps its sea-level default.
    self.temperature, self.pressure, self.humidity = parse_scene(scene)

  def get_air_density(self, unit=ureg.kg/ureg.meter**3):
    rho = air_density(self.temperature, self.pressure, self.humidity)
    return float(rho.to(unit).magnitude)

  def constants(self):
    # Resolve every run parameter to SI floats once.
    # Constants are refreshed on every Sim run and point_run
    return types.SimpleNamespace(
      g             = si_mag(self.gravitational_acceleration),
      m             = si_mag(self.ball_mass),
      Cd            = si_mag(self.drag_coefficient),
      Cm            = si_mag(self.magnus_coefficient),
      rho           = self.get_air_density(),
      magnus_model  = self.magnus_model,
      enabled_terms = tuple(self.enabled_terms) if self.enabled_terms else ALL_TERMS,
      dt            = self.time_step.to('s').magnitude,
      tol           = self.error_tolerance.to('').magnitude,
      growth        = self.time_step_growth_rate.to('').magnitude,
      auto_converge = self.auto_converge_time_step,
    )

  def _resolve_geometry(self):
    # Returns (release_world_m, arm_dir, M) — all quantities in SI base units.
    arm_slot_rad = self.arm_slot.to('radian').magnitude

    if self.arm_length is not None:
      arm_len_m = self.arm_length.to('m').magnitude
    elif self.height is not None:
      arm_len_m = _K_ARM * self.height.to('m').magnitude
    else:
      raise ValueError("Cannot resolve arm length: 'position.height' is required.")

    if self.arm_extension is not None:
      arm_ext_m = self.arm_extension.to('m').magnitude 
    else:
      arm_ext_m = _K_EXT * self.height.to('m').magnitude

    arm_dir = arm_direction(arm_slot_rad, self.handedness, arm_ext_m, arm_len_m)

    if self.release_pos is not None:
      rp = self.release_pos
      release_world = rp.to('m').magnitude if isinstance(rp, Q_) else numpy.asarray(rp, dtype=float)
    elif self.height is not None:
      height_m  = self.height.to('m').magnitude
      shoulder  = numpy.array([self.rubber[0], self.rubber[1] - _K_STRIDE * height_m, _K_SH * height_m + _MOUND_HEIGHT_M])
      release_world = shoulder + arm_len_m * arm_dir
    else:
      raise ValueError("Cannot resolve release point: provide 'position.release_pos' or 'position.height'.")

    M = build_pitch_frame(release_world, arm_dir)
    return release_world, arm_dir, M

  def point_velocity_at(self, r):
    self.aim_target      = numpy.asarray(r, dtype=float)
    self.velocity_vector = None

  def get_position(self, unit=ureg.meter):
    release_world, _, _ = self._resolve_geometry()
    return Q_(release_world, 'm').to(unit).magnitude

  def velo_correction(self, v50_ms):
    '''
    Back-compute the ball's release velocity from its Statcast-tracked velocity at y=50 ft.

    Args:
      v50_ms: velocity vector at y=50 ft, in m/s (numpy array, world frame).
    Returns:
      v_release: velocity vector at the release point, in m/s (numpy array, world frame).
    '''
    c = self.constants()
    state = numpy.zeros(10)
    state[4:7]  = v50_ms
    state[7:10] = self.get_spin()
    a = acceleration(state, c)   # all terms, using this config's own constants

    release_world, _, _ = self._resolve_geometry()
    s_y = Q_(50, 'ft').to('m').magnitude - release_world[1]

    # Solve 0.5*a_y*t^2 - v50_y*t + s_y = 0 for t > 0
    A   = 0.5 * a[1]
    B   = -v50_ms[1]
    C   = s_y
    disc = B**2 - 4*A*C
    if disc < 0:
      raise ValueError("velo_correction: no real solution, check release point and velocity vector.")
    t = (-B + numpy.sqrt(disc)) / (2 * A)

    return v50_ms - a * t

  def get_velocity(self, unit=(ureg.meter/ureg.second), suppress_velo_correction=False):
    release_world, _, _ = self._resolve_geometry()

    # direction
    if self.aim_target is not None:
      dr        = self.aim_target - release_world
      direction = dr / norm(dr)
    elif self.velocity_vector is not None:
      if isinstance(self.velocity_vector, Q_):
        vv_ms = self.velocity_vector.to('m/s').magnitude 
      else:
        vv_ms = numpy.asarray(self.velocity_vector, dtype=float)
      if self.format_type == 'statcast' and not suppress_velo_correction:
        v_release_ms = self.velo_correction(vv_ms)
        direction    = v_release_ms / norm(v_release_ms)
      else:
        direction = vv_ms / norm(vv_ms)
    else:
      raise ValueError("Cannot resolve velocity direction: provide 'velocity.target' or 'velocity.vector'.")

    # magnitude
    if self.speed is not None:
      magnitude = float(self.speed.to(unit).magnitude)
    else:
      raise ValueError("Cannot resolve speed: provide 'speed.'")
    return magnitude * direction

  def get_spin(self, unit=ureg.radian/ureg.second):
    magnitude = float(self.spin_rate.to(unit).magnitude)
    if self.format_type == 'statcast':
      # spin_angle is a world-frame tilt in the x-z plane
      # counter-clockwise from +x (catcher's view)
      # 0deg = topspin, 180deg = backspin.
      t = self.spin_angle.to('radian').magnitude
      spin_dir = numpy.array([numpy.cos(t), 0.0, numpy.sin(t)])
    else:
      _, _, M  = self._resolve_geometry()
      spin_dir = M @ (rot_axis(yhat, self.clock_angle) @ (self.spin_axis / norm(self.spin_axis)))
    return magnitude * (spin_dir / norm(spin_dir))
