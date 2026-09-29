# Joystick-style flying with a sensor loop instead of fixed distances.
from codrone_edu.drone import *

drone = Drone()
drone.pair()
drone.takeoff()

# climb until we're at green-keyhole height
while drone.get_pos_z() < 118:
    drone.set_throttle(30)
    drone.move(0.1)
drone.reset_move_values()      # otherwise the throttle stays at 30!
drone.hover(0.5)
print("at", drone.get_pos_z(), "cm")

# creep forward until we're past the keyhole
while drone.get_pos_x() < 125:
    drone.set_pitch(40)
    drone.move(0.1)
drone.reset_move_values()
drone.hover(1)
print("x =", drone.get_pos_x())

drone.land()
drone.close()
