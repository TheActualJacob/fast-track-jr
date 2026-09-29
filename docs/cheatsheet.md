# CoDrone EDU Python cheat sheet

Everything here works the same on the **real drone** and in the **simulator**. Full docs:
[docs.robolink.com → CoDrone EDU → Python](https://docs.robolink.com/docs/CoDroneEDU/Python/Drone-Function-Documentation/)

## Every program starts and ends like this

```python
from codrone_edu.drone import *

drone = Drone()
drone.pair()          # connect to the controller plugged into your computer

# ... your flight ...

drone.close()         # disconnect at the very end
```

## Take off, hover, land

| Code | What it does |
|---|---|
| `drone.takeoff()` | Climbs to **about 80 cm** and hovers. Takes ~4 s. |
| `drone.hover(2)` | Stay still for 2 seconds. |
| `drone.land()` | Lands right where it is. Takes ~4 s. |
| `drone.emergency_stop()` | Motors **off**. It drops out of the air! Emergencies only. |

## Move a set distance (easiest and most accurate)

```python
drone.move_forward(100)          # 100 cm (cm is the default unit)
drone.move_backward(50)
drone.move_left(30)
drone.move_right(30)
drone.move_upward(40)
drone.move_downward(20)

drone.move_forward(3, "ft")      # units: "cm", "in", "ft", "m"
drone.move_forward(100, "cm", 1) # 3rd number = speed in metres/second (default 0.5, max 2)

drone.move_distance(1.0, -0.5, 0.2, 0.5)   # METRES: forward, LEFT, up, speed
```

- Directions are **relative to where the drone is facing**. After `turn_right(90)`, "forward" points the new way.
- In `move_distance`, **positive y is LEFT** and negative y is right.
- Each move takes about *distance ÷ speed + 1 second* (the drone settles before the next command).

## Turn

```python
drone.turn_left(90)      # degrees
drone.turn_right(90)
drone.turn_degree(-90)   # face an exact heading: 0 = the way you took off, + = left, - = right
```

> **Heads up:** turns can overshoot by a few degrees, just like the real drone. Over 2 m, a 3° error puts you
> 10 cm off target. `move_left()` / `move_right()` let you go sideways **without turning**.

## Joystick-style flying (like the controller)

```python
drone.set_pitch(50)      # + forward,  - backward
drone.set_roll(-30)      # + right,    - left
drone.set_throttle(40)   # + up,       - down
drone.set_yaw(20)        # + turn left, - turn right
drone.move(1.5)          # fly with those values for 1.5 seconds
drone.hover(1)

drone.go("forward", 50, 2)   # direction, power 0–100, seconds ("forward", "backward", "left", "right", "up", "down")
```

> **Classic bug:** the values **stay set** until you change them. After `set_throttle(40)` + `move(1)`, the next
> `move()` keeps climbing too! Use `drone.reset_move_values()` to zero everything.

In the simulator, power 50 is about 50 cm/s. Your real drone will be a bit different, so test it!

## Sensors

| Code | Gives you |
|---|---|
| `drone.get_pos_z()` | Height since takeoff, cm. Works at any height. |
| `drone.get_height()` | cm down to whatever is below (floor, cube...). **Above 150 cm it returns 999.9!** |
| `drone.get_pos_x()` | cm forward since takeoff (always measured along the takeoff direction). |
| `drone.get_pos_y()` | cm **left** since takeoff (negative = right). |
| `drone.get_front_range()` | cm to whatever is in front, up to 150. `999` = nothing there. |
| `drone.get_angle_z()` | Which way it's facing, degrees. 0 at takeoff, + = turned left. |
| `drone.get_battery()` | Battery %. |

## Lights and sound

```python
drone.set_drone_LED(0, 255, 0, 100)    # red, green, blue (0–255), brightness
drone.drone_buzzer(Note.C5, 300)       # a note for 300 ms
drone.drone_buzzer(440, 300)           # or any frequency in Hz
```

## Useful patterns

```python
# climb until we reach 120 cm
while drone.get_pos_z() < 120:
    drone.set_throttle(30)
    drone.move(0.1)
drone.reset_move_values()
drone.hover(0.5)

# make your own command
def through_gate(height_change, distance):
    if height_change > 0:
        drone.move_upward(height_change)
    elif height_change < 0:
        drone.move_downward(-height_change)
    drone.move_forward(distance)

print("height:", drone.get_pos_z())   # print() shows up in the replay's console
```
