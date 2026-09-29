# The smallest useful program: take off, blink, hover, land.
from codrone_edu.drone import *

drone = Drone()
drone.pair()

drone.takeoff()
drone.set_drone_LED(0, 255, 0, 100)      # green
print("height after takeoff:", drone.get_pos_z(), "cm")
drone.hover(2)
drone.drone_buzzer(Note.C5, 200)
drone.land()

drone.close()
