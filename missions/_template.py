# ────────────────────────────────────────────────────────────────────────
#  Fast Track Jr. — my autonomous mission
#
#  1. Fill in the TODOs (course map: docs/course-map.svg)
#  2. Press Fly in the Mission Lab to test it:
#       https://theactualjacob.github.io/fast-track-jr/
#  3. Submit it. Your flight goes up on the big screen!
#
#  Distances are in centimetres. The drone starts at (0, 0) facing the red arch.
#  This exact file also flies the REAL CoDrone EDU.
# ────────────────────────────────────────────────────────────────────────
from codrone_edu.drone import *

drone = Drone()
drone.pair()

drone.takeoff()          # +5 · climbs to about 80 cm and hovers

# TODO 1 · RED ARCH (+5)
#   30 cm ahead. Anything flying forward goes under it.

# TODO 2 · GREEN KEYHOLE (+10)
#   110 cm ahead, ring center 120 cm high.
#   You're hovering at 80 cm... what has to happen first?

# TODO 3 · THE CORNER
#   175 cm ahead of the start. From here the course goes to the RIGHT.

# TODO 4 · BLUE ARCH (+5)
#   75 cm to the right of the corner.

# TODO 5 · YELLOW KEYHOLE (+20)
#   160 cm to the right of the corner, ring center 140 cm high.

# TODO 6 · LANDING PAD (+5, bullseye +15)
#   250 cm to the right of the corner.
#   Careful: the TUNNEL hangs over the pad from 95 to 143 cm high!

drone.land()
drone.close()
