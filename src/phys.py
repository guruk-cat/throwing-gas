import re
import types
import pint
import numpy
from numpy.linalg import norm
import sys


ureg = pint.UnitRegistry()
ureg.define('percent = 0.01 rad')   # convenience unit for relative error tolerances
Q_ = ureg.Quantity                  # type: ignore[misc]
pint.set_application_registry(ureg)

xhat = numpy.array([1, 0, 0], dtype=float)
yhat = numpy.array([0, 1, 0], dtype=float)
zhat = numpy.array([0, 0, 1], dtype=float)

# pitcher body proportion constants (used when precise values are not provided)
_K_SH           = 0.63    # shoulder height as fraction of pitcher height during delivery (absorbs knee bend + forward lean)
_K_ARM          = 0.37    # arm length as fraction of pitcher height
_K_EXT          = 0.082   # arm extension (forward lean) as fraction of pitcher height (~15 cm for 182 cm pitcher)
_K_STRIDE       = 0.85    # shoulder stride toward plate as fraction of pitcher height (back-computed from Statcast avg ~5.75 ft extension)
_MOUND_HEIGHT_M = 0.254   # standard mound height above field level (10 in)


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

def si_mag(quant):
  # Strip pint quantity to its SI base-unit magnitude.
  return quant.to_base_units().magnitude

def _parse_quantity(s):
  # Handle "X ft Y in" compound format not natively supported by pint.
  # Plain numbers default to metres.
  if isinstance(s, (int, float)):
    return Q_(float(s), 'm')
  m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*ft\s+(\d+(?:\.\d+)?)\s*in\s*$', s)
  if m:
    return Q_(float(m.group(1)) * 12 + float(m.group(2)), 'in')
  return Q_(s)

def arm_direction(arm_slot_rad, handedness, arm_extension_m=0.0, arm_length_m=1.0):
  # Unit vector from shoulder to hand at release, in world coordinates.
  # Righty arm is on world -x side (pitcher's right); lefty on +x.
  sign  = -1.0 if handedness.lower().startswith('r') else 1.0
  e     = arm_extension_m / arm_length_m   # normalised forward lean ∈ [0, 1)
  scale = numpy.sqrt(1.0 - e**2)          # lateral/vertical amplitude shrinks as arm leans forward
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


class Simulation:
  def __init__(self):
    self.config = types.SimpleNamespace()
    self.config.wind_speed                  = Q_(0, 'mph')
    self.config.wind_direction              = Q_(0, 'degree')
    self.config.drag_coefficient            = Q_(0.0007884037809624002, 'kg/m')
    self.config.magnus_coefficient          = Q_(2.2075e-06, 'kg * s / m')
    self.config.magnus_model                = 'squared velocity'
    self.config.ball_mass                   = Q_(145, 'g')
    self.config.ball_diameter               = Q_(3, 'in')
    self.config.gravitational_acceleration  = Q_(9.8, 'm/s**2')
    self.config.time_step                   = Q_(0.25, 'ms')
    self.config.time_step_growth_rate       = Q_(1, '')
    self.config.error_tolerance             = Q_(0.1, 'percent')
    self.config.auto_converge_time_step     = True

  def configure(self, config):
    config_keys_used = []
    for k in self.config.__dict__:
      config_key = None
      if k in config:
        config_key = k
      if k.replace("_", " ") in config:
        config_key = k.replace("_", " ")

      if config_key is not None:
        config_keys_used.append(config_key)
        new_val = Q_(config[config_key])
        if new_val.dimensionality != self.config.__dict__[k].dimensionality:
          raise Exception(f"Configuration parameter '{config_key}' has wrong dimensions. "
                          f"Expected '{self.config.__dict__[k].dimensionality}' "
                          f"but got '{new_val.dimensionality}'.")
        self.config.__dict__[k] = new_val

    if len(config_keys_used) != len(config.keys()):
      print("Warning: there were unused keys when configuring Simulation:")
      for k in list(set(config.keys()) - set(config_keys_used)):
        print("  ", k)
      print("Make sure you didn't mispell something.")

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

  def derivative(self, state):
    dsdt = numpy.zeros(self.state_size)

    dsdt[0]   = 1           # dt/dt = 1
    dsdt[1:4] = state[4:7]  # dx/dt = v
    # dw/dt = 0 (spin treated as constant for now)

    # dv/dt = (Fg + Fd + Fm) / m
    dsdt[4:7] -= si_mag(self.config.gravitational_acceleration) * zhat  # gravity
    speed = norm(state[4:7])
    dsdt[4:7] -= si_mag(self.config.drag_coefficient) * speed * state[4:7] / si_mag(self.config.ball_mass)  # drag
    if self.config.magnus_model == 'squared velocity':
      dsdt[4:7] += si_mag(self.config.magnus_coefficient) * speed * numpy.cross(state[7:10], state[4:7]) / si_mag(self.config.ball_mass)
    elif self.config.magnus_model == 'linear velocity':
      dsdt[4:7] += si_mag(self.config.magnus_coefficient) * numpy.cross(state[7:10], state[4:7]) / si_mag(self.config.ball_mass)
    else:
      raise Exception(f"Unrecognized magnus model '{self.config.magnus_model}'")

    return dsdt

  def rk4(self, time_step, state):
    k1 = time_step * self.derivative(state)
    k2 = time_step * self.derivative(state + k1 / 2)
    k3 = time_step * self.derivative(state + k2 / 2)
    k4 = time_step * self.derivative(state + k3)
    return state + (k1 + 2*k2 + 2*k3 + k4) / 6

  def _step_error(self, s0, s1, s2):
    # relative error: how much the double-half-step s2 differs from the full-step s1,
    # normalised by the total displacement from s0
    return norm(s2 - s1) / norm(s2 - s0)

  def run(self, launch_config, terminate_function=lambda record: len(record) > 1000, record_all=True, adaptive=True):
    state = numpy.zeros(self.state_size)
    state[1:4]  = launch_config.get_position()
    state[4:7]  = launch_config.get_velocity()
    state[7:10] = launch_config.get_spin()

    record = [state.copy()]
    dt = self.config.time_step.to('s').magnitude

    while not terminate_function(record):
      # adaptive step: compare one full step vs two half steps; halve dt if error too large
      while adaptive:
        s1  = self.rk4(dt, state)
        s2  = self.rk4(dt/2, self.rk4(dt/2, state))
        err = self._step_error(state, s1, s2)
        if self.config.auto_converge_time_step and err > self.config.error_tolerance.to('').magnitude:
          print(f"Info: decreasing time step from {dt} to {dt/2}")
          dt /= 2
        else:
          state = s2
          break

      if not adaptive:
        state = self.rk4(dt, state)
      if adaptive:
        dt *= self.config.time_step_growth_rate.to('').magnitude

      if record_all:
        record.append(state.copy())
      else:
        record[0] = state.copy()

    return record


class Configuration:
  def __init__(self):
    # Arm geometry parameters
    self.handedness    = 'right'
    self.arm_slot      = Q_(45, 'degree')
    self.arm_extension = None              # Q_; if None, derived from height via _K_EXT
    self.arm_length    = None              # Q_; if None, derived from height via _K_ARM

    # Position parameters — provide one of:
    #   release_pos  : direct world-frame release point (e.g. from Statcast)
    #   height       : pitcher height; shoulder estimated from rubber + _K_SH * height
    self.release_pos   = None              # Q_ vector or ndarray (metres)
    self.height        = None              # Q_
    self.rubber        = numpy.array([0.0, 18.44])  # [x_m, y_m]

    # Velocity parameters
    self.speed           = None            # Q_ scalar; if None, derived from velocity_vector norm
    self.aim_target      = None            # ndarray (world metres); mutually exclusive with velocity_vector
    self.velocity_vector = None            # Q_ vector; mutually exclusive with aim_target

    # Spin parameters
    self.spin        = Q_(0, 'rad/s')
    self.spin_axis   = xhat.copy()         # unit vector in pitch-frame coordinates
    self.clock_angle = Q_(0, 'degree')

  def configure(self, config):
    config_keys_used = []

    for key, attr, parser in [
      ('handedness',    'handedness',    lambda v: v),
      ('arm_slot',      'arm_slot',      _parse_quantity),
      ('arm_extension', 'arm_extension', _parse_quantity),
      ('arm_length',    'arm_length',    _parse_quantity),
      ('speed',         'speed',         _parse_quantity),
      ('spin',          'spin',          _parse_quantity),
      ('clock_angle',   'clock_angle',   _parse_quantity),
    ]:
      if key in config:
        setattr(self, attr, parser(config[key]))
        config_keys_used.append(key)

    if 'position' in config:
      pos = config['position']
      config_keys_used.append('position')
      if 'height' not in pos:
        raise ValueError("'position.height' is required.")
      self.height = _parse_quantity(pos['height'])
      if 'release_pos' in pos:
        rp = pos['release_pos']
        units = Q_(rp[0]).units
        self.release_pos = units * numpy.array([Q_(v).to(units).magnitude for v in rp])
      if 'rubber' in pos:
        r = pos['rubber']
        self.rubber = numpy.array([_parse_quantity(r[0]).to('m').magnitude,
                                   _parse_quantity(r[1]).to('m').magnitude])

    if 'velocity' in config:
      vel = config['velocity']
      config_keys_used.append('velocity')
      if 'target' in vel:
        t = vel['target']
        self.aim_target      = numpy.array([_parse_quantity(v).to('m').magnitude for v in t])
        self.velocity_vector = None
      elif 'vector' in vel:
        v = vel['vector']
        units = Q_(v[0]).units
        self.velocity_vector = units * numpy.array([Q_(x).to(units).magnitude for x in v])
        self.aim_target      = None
      else:
        raise ValueError("'velocity' must contain 'target' or 'vector'.")

    if 'spin_axis' in config:
      ax = numpy.asarray(config['spin_axis'], dtype=float)
      self.spin_axis = ax / norm(ax)
      config_keys_used.append('spin_axis')

    if len(config_keys_used) != len(config.keys()):
      print("Warning: there were unused keys when configuring LaunchConfiguration:")
      for k in list(set(config.keys()) - set(config_keys_used)):
        print("  ", k)
      print("Make sure you didn't mispell something.")

  def _resolve_geometry(self):
    # Returns (release_world_m, arm_dir, M) — all quantities in SI base units.
    arm_slot_rad = self.arm_slot.to('radian').magnitude

    if self.arm_length is not None:
      arm_len_m = self.arm_length.to('m').magnitude
    elif self.height is not None:
      arm_len_m = _K_ARM * self.height.to('m').magnitude
    else:
      raise ValueError("Cannot resolve arm length: 'position.height' is required.")

    arm_ext_m = self.arm_extension.to('m').magnitude if self.arm_extension is not None \
                else _K_EXT * self.height.to('m').magnitude

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

  def get_velocity(self, unit=(ureg.meter/ureg.second)):
    release_world, _, _ = self._resolve_geometry()

    if self.aim_target is not None:
      dr        = self.aim_target - release_world
      direction = dr / norm(dr)
    elif self.velocity_vector is not None:
      vv_ms     = self.velocity_vector.to('m/s').magnitude if isinstance(self.velocity_vector, Q_) \
                  else numpy.asarray(self.velocity_vector, dtype=float)
      direction = vv_ms / norm(vv_ms)
    else:
      raise ValueError("Cannot resolve velocity direction: provide 'velocity.target' or 'velocity.vector'.")

    if self.speed is not None:
      magnitude = float(self.speed.to(unit).magnitude)
    elif self.velocity_vector is not None:
      vv        = self.velocity_vector
      vv_u      = vv.to(unit).magnitude if isinstance(vv, Q_) else numpy.asarray(vv, dtype=float)
      magnitude = float(norm(vv_u))
    else:
      raise ValueError("Cannot resolve speed: provide 'speed' or 'velocity.vector'.")

    return magnitude * direction

  def get_spin(self, unit=ureg.radian/ureg.second):
    _, _, M  = self._resolve_geometry()
    spin_ax  = self.spin_axis / norm(self.spin_axis)
    clock_R  = rot_axis(yhat, self.clock_angle)
    spin_dir = M @ (clock_R @ spin_ax)
    return float(self.spin.to(unit).magnitude) * (spin_dir / norm(spin_dir))
