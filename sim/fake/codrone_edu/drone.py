"""
Simulator stand-in for `codrone_edu.drone`.

Same function names, arguments and (roughly) the same timing as the real library
(codrone-edu 2.10), so a mission that runs here also runs on the real drone, and the other
way round. Instead of talking to a controller over USB, every call drives the virtual drone
in sim/engine.py.
"""
import difflib
import functools
import math
import time

from codrone_edu.protocol import Note
from codrone_edu.system import ModeFlight, ModeMovement
from sim import engine as _engine

__all__ = ["Drone", "Note", "ModeFlight", "ModeMovement", "time", "sleep"]

_UNITS_CM = {"cm": 1.0, "m": 100.0, "mm": 0.1, "in": 2.54, "ft": 30.48}

# Public methods of the real codrone_edu Drone class (v2.10). Anything on this list that we
# don't simulate becomes a harmless no-op; anything NOT on it is a typo -> AttributeError.
_REAL_METHODS = set("""
add_callback append_color_data avoid_wall check checkDetail circle circle_turn close connect control_change
controller_LED_off controller_buzzer controller_buzzer_sequence controller_clear_screen controller_create_canvas
controller_draw_arc controller_draw_canvas controller_draw_chord controller_draw_ellipse controller_draw_image
controller_draw_line controller_draw_point controller_draw_polygon controller_draw_rectangle controller_draw_square
controller_draw_string controller_draw_string_align controller_preview_canvas convert_meter convert_millimeter
detect_colors detect_wall disconnect down_arrow_pressed drone_LED_off drone_buzzer drone_buzzer_sequence
dummy_function emergency_stop flip getCount getData getHeader get_accel_x get_accel_y get_accel_z
get_accident_count get_ack_data get_address_data get_altitude_data get_angle_x get_angle_y get_angle_z
get_angular_speed_x get_angular_speed_y get_angular_speed_z get_back_color get_battery get_bottom_range
get_button_data get_color_data get_colors get_control_speed get_count_data get_cpu_id_data get_drone_temperature
get_elevation get_error_data get_flight_state get_flight_time get_flow_data get_flow_velocity_x
get_flow_velocity_y get_flow_x get_flow_y get_front_color get_front_range get_height get_image_data
get_information_data get_joystick_data get_landing_count get_left_joystick_x get_left_joystick_y
get_lostconnection_data get_motion_data get_move_values get_movement_state get_pos_x get_pos_y get_pos_z
get_position_data get_pressure get_range_data get_raw_motion_data get_right_joystick_x get_right_joystick_y
get_sensor_data get_state_data get_system_state get_takeoff_count get_temperature get_trim get_trim_data
get_x_accel get_x_angle get_x_gyro get_y_accel get_y_angle get_y_gyro get_z_accel get_z_angle get_z_gyro go
goto_waypoint h_pressed headless_change height_from_pressure hover initialize_data isConnected isOpen
keep_distance l1_pressed l2_pressed land left_arrow_pressed load_classifier load_color_data
load_color_data_without_print makeTransferDataArray move move_backward move_distance move_downward move_forward
move_left move_right move_upward new_color_data open p_pressed pair percent_error ping power_pressed
predict_colors print_move_values print_num_data r1_pressed r2_pressed receive_address_data receive_cpu_id_data
reset_classifier reset_gyro reset_move reset_move_values reset_previous_land reset_sensor reset_trim
right_arrow_pressed s_pressed sendBacklight sendBuzzer sendBuzzerHz sendBuzzerHzReserve sendBuzzerMute
sendBuzzerMuteReserve sendBuzzerScale sendBuzzerScaleReserve sendClearBias sendClearTrim sendCommand
sendCommandLightEvent sendCommandLightEventColor sendCommandLightEventColors sendControl sendControlPosition
sendControlWhile sendControlleLinkMode sendDisplayClear sendDisplayClearAll sendDisplayDrawCircle
sendDisplayDrawLine sendDisplayDrawPoint sendDisplayDrawRect sendDisplayDrawString sendDisplayDrawStringAlign
sendDisplayInvert sendFlightEvent sendFlip sendHeadless sendLanding sendLightDefaultColor sendLightEventColor
sendLightEventColors sendLightManual sendLightModeColor sendLightModeColors sendLostConnection
sendModeControlFlight sendMotor sendMotorSingle sendPairing sendPing sendRequest sendSetDefault sendStop
sendTakeOff sendTrim sendVibrator sendVibratorReserve sendWeight send_absolute_position setEventHandler
set_controller_LED set_controller_LED_mode set_drone_LED set_drone_LED_mode set_initial_pressure set_motor_speed
set_pitch set_roll set_throttle set_trim set_waypoint set_yaw speed_change spiral square start_controller_buzzer
start_drone_buzzer stop_controller_buzzer stop_drone_buzzer stop_motors sway takeoff transfer triangle
triangle_turn turn turn_degree turn_direction turn_left turn_right up_arrow_pressed update_ack_data update_address
update_altitude_data update_color_data update_count_data update_cpu_id_data update_error_data update_flow_data
update_information update_joystick_data update_lostconnection_data update_motion_data update_position_data
update_range_data update_raw_motion_data update_state_data update_trim_data
""".split())


def sleep(seconds):
    # `from codrone_edu.drone import *` hands out time + sleep on the real library too
    time.sleep(seconds)


def _S():
    return _engine.current()


def _fmt(v):
    if isinstance(v, float):
        return f"{v:g}"
    if hasattr(v, "name") and hasattr(v, "value"):
        return f"{type(v).__name__}.{v.name}"
    return repr(v)


def _api(fn):
    """Log each top-level call (for the replay's code highlighting) and keep nested calls quiet."""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        S = _S()
        outer = S.depth == 0
        if outer:
            stack = S.caller_lines()
            line = stack[0] if stack else None
            S.cur_line = line
            S.cur_outer = stack[1:]
            t0 = S.t
            parts = [_fmt(a) for a in args] + [f"{k}={_fmt(v)}" for k, v in kwargs.items()]
            text = f"drone.{fn.__name__}({', '.join(parts)})"
            if not S.paired and fn.__name__ not in ("pair", "connect", "open"):
                S.warn_once("pair", "drone.pair() was never called — on the real drone nothing would fly!")
        S.depth += 1
        try:
            return fn(self, *args, **kwargs)
        finally:
            S.depth -= 1
            if outer:
                call = {"t0": round(t0, 3), "t1": round(S.t, 3), "line": line, "text": text}
                if len(stack) > 1:
                    call["outer"] = stack[1:]   # where a helper function was called from
                S.calls.append(call)
    return wrapper


def _cm(value, units):
    if units not in _UNITS_CM or units == "mm":
        print("Error: Not a valid unit.")
        return None
    return float(value) * _UNITS_CM[units]


def _out(cm, unit):
    return cm / _UNITS_CM.get(unit, 1.0)


def _note_hz(note):
    if isinstance(note, Note):
        return 32.703 * 2 ** (note.value / 12.0)
    return float(note)


class Drone:
    def __init__(self, *args, **kwargs):
        self._control = [0, 0, 0, 0]  # roll, pitch, yaw, throttle
        self.waypoint_data = []

    # ------------------------------------------------------------------ connection
    @_api
    def pair(self, portname=None):
        S = _S()
        S.paired = True
        print("[sim] Paired with the virtual CoDrone EDU")
        S.advance(0.5)

    connect = pair
    open = pair

    @_api
    def close(self):
        S = _S()
        S.closed = True
        if S.flying():
            S.warn_once("close_flying", "drone.close() was called while the drone was still flying.")

    disconnect = close

    def isConnected(self):
        return _S().paired

    isOpen = isConnected

    # ------------------------------------------------------------------ takeoff / land
    @_api
    def takeoff(self):
        S = _S()
        self.reset_move_values()
        S.cmd_takeoff()
        S.advance(0.03)
        S.advance(4.0)

    @_api
    def land(self):
        S = _S()
        self.reset_move_values()
        S.advance(0.02)
        S.cmd_land()
        S.advance(0.01)
        S.advance(4.0)

    @_api
    def emergency_stop(self):
        self._control = [0, 0, 0, 0]
        _S().cmd_stop()
        _S().advance(0.01)

    stop_motors = emergency_stop

    @_api
    def hover(self, duration=0.01):
        S = _S()
        S.cmd_sticks(0, 0, 0, 0)
        S.advance(duration)

    @_api
    def reset_move_values(self, attempts=3):
        self._control = [0, 0, 0, 0]
        for _ in range(attempts):
            _S().cmd_sticks(0, 0, 0, 0)
            _S().advance(0.01)

    reset_move = reset_move_values

    # ------------------------------------------------------------------ joystick-style control
    @staticmethod
    def _clip(power):
        return max(-100, min(100, int(power)))

    def set_roll(self, power):
        self._control[0] = self._clip(power)

    def set_pitch(self, power):
        self._control[1] = self._clip(power)

    def set_yaw(self, power):
        self._control[2] = self._clip(power)

    def set_throttle(self, power):
        self._control[3] = self._clip(power)

    def get_move_values(self):
        return list(self._control)

    def print_move_values(self):
        print(*self._control)

    @_api
    def move(self, duration=None):
        S = _S()
        S.cmd_sticks(*self._control)
        S.advance(0.003 if duration is None else duration)

    @_api
    def sendControl(self, roll, pitch, yaw, throttle):
        _S().cmd_sticks(roll, pitch, yaw, throttle)
        _S().advance(0.003)

    @_api
    def sendControlWhile(self, roll, pitch, yaw, throttle, timeMs):
        _S().cmd_sticks(roll, pitch, yaw, throttle)
        _S().advance(timeMs / 1000.0)

    @_api
    def go(self, direction, power=50, duration=1):
        self._control = [0, 0, 0, 0]
        power = max(0, min(100, power))
        axis = {"forward": (1, 1), "backward": (1, -1), "right": (0, 1), "left": (0, -1),
                "up": (3, 1), "down": (3, -1)}.get(str(direction).lower())
        if axis is None:
            print("Warning: Invalid arguments. Please check your parameters.")
            return
        self._control[axis[0]] = int(power * axis[1])
        self.move(duration)
        self.hover(0.8)

    @_api
    def turn(self, power=50, seconds=None):
        S = _S()
        if seconds is None:
            S.cmd_sticks(0, 0, self._clip(power), 0)
            S.advance(0.003)
        else:
            S.cmd_sticks(0, 0, self._clip(power), 0)
            S.advance(seconds)
            self.hover(0.5)

    # ------------------------------------------------------------------ turning (gyro loops, like the real library)
    @_api
    def turn_direction(self, degree=90, timeout=3, p_value=10):
        S = _S()
        self.hover(0.1)
        degree = int(degree)
        if degree == 0:
            return
        dist = min(abs(degree), 360)
        sign = 1 if degree > 0 else -1
        if dist > 180:
            timeout *= 2
        prev = self.get_angle_z()
        t_end = S.t + timeout
        while S.t < t_end:
            cur = self.get_angle_z()
            dist -= abs(_engine.wrap180(cur - prev))
            prev = cur
            if dist <= 0:
                self.hover(0.1)
                break
            speed = max(5, min(100, int(int(dist / 360 * 100) * p_value)))
            S.cmd_sticks(0, 0, sign * speed, 0)
            S.advance(0.005)
        self.hover(0.8)

    @_api
    def turn_left(self, degree=90):
        self.turn_direction(min(int(abs(degree)), 360))

    @_api
    def turn_right(self, degree=90):
        self.turn_direction(-min(int(abs(degree)), 360))

    @_api
    def turn_degree(self, degree=90, timeout=3, p_value=10):
        """Turn to an absolute heading (relative to takeoff). Positive = left."""
        S = _S()
        self.hover(0.01)
        target = _engine.wrap180(degree)
        t_end = S.t + timeout
        while S.t < t_end:
            err = _engine.wrap180(target - self.get_angle_z())
            if err == 0:
                break
            speed = max(-100, min(100, int(int(abs(err) / 360 * 100) * p_value)))
            S.cmd_sticks(0, 0, speed if err > 0 else -speed, 0)
            S.advance(0.005)
        self.hover(0.05)

    # ------------------------------------------------------------------ distance moves (onboard position control)
    def _relative(self, fwd, left, up, speed_ms, extra_wait=1.0):
        S = _S()
        speed_ms = max(0.0, min(2.0, speed_ms))
        dist_m = math.sqrt(fwd ** 2 + left ** 2 + up ** 2) / 100.0
        if speed_ms == 0:
            raise ZeroDivisionError("speed must be bigger than 0")
        S.cmd_relative(fwd, left, up, speed_ms * 100.0)
        S.advance(0.1)
        S.advance(0.01)  # get_movement_state()
        S.advance(dist_m / speed_ms + extra_wait)

    @_api
    def move_forward(self, distance, units="cm", speed=0.5):
        d = _cm(distance, units)
        if d is not None:
            self._relative(d, 0, 0, speed)

    @_api
    def move_backward(self, distance, units="cm", speed=0.5):
        d = _cm(distance, units)
        if d is not None:
            self._relative(-d, 0, 0, speed)

    @_api
    def move_left(self, distance, units="cm", speed=0.5):
        d = _cm(distance, units)
        if d is not None:
            self._relative(0, d, 0, speed)

    @_api
    def move_right(self, distance, units="cm", speed=0.5):
        d = _cm(distance, units)
        if d is not None:
            self._relative(0, -d, 0, speed)

    @_api
    def move_upward(self, distance, units="cm", speed=0.5):
        d = _cm(distance, units)
        if d is not None:
            self._relative(0, 0, d, speed)

    @_api
    def move_downward(self, distance, units="cm", speed=0.5):
        d = _cm(distance, units)
        if d is not None:
            self._relative(0, 0, -d, speed)

    @_api
    def move_distance(self, positionX, positionY, positionZ, velocity):
        """Metres, relative to where the drone is and the way it's facing (+x fwd, +y left, +z up)."""
        if velocity <= 0:
            raise ZeroDivisionError("velocity must be bigger than 0")
        self._relative(positionX * 100, positionY * 100, positionZ * 100, velocity, extra_wait=1.25)

    @_api
    def sendControlPosition(self, positionX, positionY, positionZ, velocity, heading, rotationalVelocity):
        S = _S()
        S.cmd_relative(positionX * 100, positionY * 100, positionZ * 100, max(0.05, velocity) * 100)
        if heading:
            S.yaw_target = _engine.wrap180(S.yaw + heading)
            S.yaw_speed = abs(rotationalVelocity) or 60
        S.advance(0.003)

    @_api
    def send_absolute_position(self, positionX, positionY, positionZ, velocity, heading, rotationalVelocity):
        """Metres, measured from the FIRST takeoff spot and heading. heading in degrees (+ = left)."""
        S = _S()
        for name, v in (("positionX", positionX), ("positionY", positionY), ("positionZ", positionZ),
                        ("velocity", velocity)):
            if not isinstance(v, (int, float)):
                print(f"Error: {name} must be an int or float.")
                return
        if not isinstance(heading, int) or not isinstance(rotationalVelocity, int):
            print("Error: heading or rotationalVelocity must be an int.")
            return
        S.advance(0.15)
        x0, y0, z0 = S.p
        S.cmd_absolute(positionX * 100, positionY * 100, positionZ * 100, velocity * 100, heading,
                       rotationalVelocity)
        dist = math.dist((x0, y0, z0), S.target) / 100 if S.target else 0
        dh = abs(_engine.wrap180(heading - self.get_angle_z()))
        wait = dist / velocity + 1 if velocity else 1
        if rotationalVelocity:
            wait = max(wait, dh / abs(rotationalVelocity) + 1)
        S.advance(0.1)
        S.advance(wait + 1.25)

    @_api
    def set_waypoint(self):
        S = _S()
        ox, oy, oz, oyaw = S.origin or S.home
        x, y = _engine.rot(S.p[0] - ox, S.p[1] - oy, -oyaw)
        wp = [round(x / 100, 3), round(y / 100, 3), round((S.p[2] - oz) / 100, 3)]
        self.waypoint_data.append(wp)
        return wp

    @_api
    def goto_waypoint(self, waypoint, velocity):
        wp = self.waypoint_data[waypoint] if isinstance(waypoint, int) else waypoint
        self.send_absolute_position(wp[0], wp[1], wp[2], velocity, int(round(self.get_angle_z())), 0)

    # ------------------------------------------------------------------ sensor-based behaviours
    @_api
    def avoid_wall(self, timeout=2, distance=70):
        S = _S()
        t_end, count = S.t + timeout, 0
        while S.t < t_end:
            cur = self.get_front_range("cm")
            speed = int(self.percent_error(distance, cur) * 0.4)
            if cur > distance + 20 or cur < distance - 20:
                S.cmd_sticks(0, max(-100, min(100, speed)), 0, 0)
                S.advance(0.005)
            else:
                self.hover()
                count += 1
                if count == 20:
                    break
        self.hover()

    @_api
    def keep_distance(self, timeout=2, distance=50):
        S = _S()
        t_end = S.t + timeout
        while S.t < t_end:
            cur = self.get_front_range("cm")
            speed = int(self.percent_error(distance, cur) * 0.4)
            if cur > distance + 10 or cur < distance - 10:
                S.cmd_sticks(0, max(-100, min(100, speed)), 0, 0)
                S.advance(0.005)
            else:
                self.hover()

    @_api
    def detect_wall(self, distance=50):
        return self.get_front_range("cm") < distance

    @staticmethod
    def percent_error(desired, current):
        return max(-100, min(100, (current - desired) / max(desired, 1) * 100))

    @_api
    def flip(self, direction="back"):
        S = _S()
        if S.battery < 50:
            print("Warning: Unable to perform flip; battery level is below 50%.")
            return
        S.cmd_flip(direction)
        S.advance(3.0)

    # ------------------------------------------------------------------ sensors
    def _read(self):
        _S().advance(0.01)  # every sensor read is a round trip over the radio

    @_api
    def get_height(self, unit="cm"):
        return self.get_bottom_range(unit)

    @_api
    def get_bottom_range(self, unit="cm"):
        self._read()
        h = _S().height()
        if h > 150:
            return 999.9  # out of range, just like the real sensor
        return round(_out(h, unit), 1)

    @_api
    def get_front_range(self, unit="cm"):
        self._read()
        d = _S().front_range()
        if d is None:
            return 999
        return round(_out(d, unit), 1)

    @_api
    def get_range_data(self, delay=0.01):
        self._read()
        S = _S()
        f = S.front_range()
        return [round(S.t, 3), 999 if f is None else round(f * 10), round(S.height() * 10)]

    @_api
    def get_pos_x(self, unit="cm"):
        self._read()
        return round(_out(_S().local_pos()[0], unit), 1)

    @_api
    def get_pos_y(self, unit="cm"):
        self._read()
        return round(_out(_S().local_pos()[1], unit), 1)

    @_api
    def get_pos_z(self, unit="cm"):
        self._read()
        return round(_out(_S().local_pos()[2], unit), 1)

    @_api
    def get_position_data(self, delay=0.01):
        self._read()
        x, y, z = _S().local_pos()
        return [round(_S().t, 3), round(x / 100, 3), round(y / 100, 3), round(z / 100, 3)]

    @_api
    def get_angle_z(self):
        self._read()
        return round(_S().angle_z(), 1)

    @_api
    def get_angle_x(self):
        self._read()
        return round(_S().tilt[0], 1)

    @_api
    def get_angle_y(self):
        self._read()
        return round(_S().tilt[1], 1)

    get_z_angle = get_angle_z
    get_x_angle = get_angle_x
    get_y_angle = get_angle_y

    @_api
    def get_battery(self):
        self._read()
        return int(_S().battery)

    @_api
    def get_flight_state(self):
        self._read()
        return {"landed": ModeFlight.Ready, "takeoff": ModeFlight.TakeOff, "flying": ModeFlight.Flight,
                "landing": ModeFlight.Landing, "falling": ModeFlight.Accident, "crashed": ModeFlight.Accident,
                "dropped": ModeFlight.Stop}[_S().mode]

    @_api
    def get_movement_state(self):
        self._read()
        S = _S()
        if S.mode == "landed":
            return ModeMovement.Ready
        moving = math.sqrt(sum(v * v for v in S.v)) > 3 or abs(S.yaw_rate) > 5
        return ModeMovement.Moving if moving else ModeMovement.Hovering

    @_api
    def get_colors(self, kind="name"):
        self._read()
        c = _S().ground_colors()
        if c is None:
            _S().warn_once("colors", "Color sensors only work when the drone is sitting on something (landed).")
            return ["unknown", "unknown"]
        return [c, c]

    def get_front_color(self, kind="name"):
        return self.get_colors(kind)[0]

    def get_back_color(self, kind="name"):
        return self.get_colors(kind)[1]

    @_api
    def get_temperature(self, unit="C"):
        self._read()
        return 22.0 if unit == "C" else 71.6

    get_drone_temperature = get_temperature

    # ------------------------------------------------------------------ lights & sound
    @_api
    def set_drone_LED(self, r, g, b, brightness=255):
        S = _S()
        k = max(0, min(255, brightness)) / 255
        S.led = [int(r * k), int(g * k), int(b * k)]
        S.leds.append({"t": round(S.t, 3), "rgb": S.led})
        S.advance(0.01)

    @_api
    def set_drone_LED_mode(self, r, g, b, mode=None, speed=None):
        self.set_drone_LED(r, g, b, 255)

    @_api
    def drone_LED_off(self):
        self.set_drone_LED(0, 0, 0, 0)

    @_api
    def drone_buzzer(self, note, duration):
        S = _S()
        S.sounds.append({"t": round(S.t, 3), "hz": round(_note_hz(note), 1), "ms": duration})
        S.advance(duration / 1000.0)

    controller_buzzer = drone_buzzer

    @_api
    def start_drone_buzzer(self, note):
        S = _S()
        S.sounds.append({"t": round(S.t, 3), "hz": round(_note_hz(note), 1), "ms": 1000})

    start_controller_buzzer = start_drone_buzzer

    @_api
    def ping(self, r=None, g=None, b=None):
        import random
        if r is None or g is None or b is None:
            r, g, b = (random.randint(0, 255) for _ in range(3))
        self.set_drone_LED(r, g, b, 255)
        self.drone_buzzer(1000, 200)

    # ------------------------------------------------------------------ anything else
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in _REAL_METHODS:
            def _noop(*args, **kwargs):
                S = _S()
                S.warn_once("noop:" + name, f"drone.{name}() isn't simulated — it was skipped.")
                S.advance(0.01)
            return _noop
        close = difflib.get_close_matches(name, sorted(_REAL_METHODS) + [
            "move_forward", "move_backward", "move_left", "move_right", "move_upward", "move_downward"], n=1)
        hint = f" Did you mean drone.{close[0]}()?" if close else ""
        raise AttributeError(f"'Drone' object has no attribute '{name}'.{hint}")
