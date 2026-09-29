# Live demo for the intro: run with   python fly.py examples/live_demo.py --watch
# It crashes into the green keyhole. Add   drone.move_upward(40)   before the move and save!
from codrone_edu.drone import *

drone = Drone()
drone.pair()

drone.takeoff()
drone.move_forward(175)
drone.land()

drone.close()
