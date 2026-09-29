# ────────────────────────────────────────────────────────────────────────
#  Official Mission 2027: Fast Track solo field — practice mission
#
#  Fly it in the simulator:   python fly.py training/<you>.py --field real
#  Look around the field:     python fly.py --course --field real
#
#  Start spot (0, 0) is 6 in onto the first mat, facing the red arch.
#  x = forward, y = left (negative = right), z = up. All in cm.
#  Element centers (from the REC setup instructions, ±3 in at events):
#   Red arch         46 cm forward
#   Landing pad      84 cm forward
#   Green keyhole    168 cm forward, 8 cm left, center 145 cm high
#   Large cube       250 cm forward, 51 cm tall
#   Mini keyhole 1   411 cm forward, 39 cm right, center 64 cm high
#   Mini keyhole 2   443 cm forward, 8 cm right, center 89 cm high
#   Mini keyhole 3   411 cm forward, 24 cm left, center 114 cm high
#   Blue arch        419 cm forward, 84 cm right
#   Yellow keyhole   411 cm forward, 165 cm right, center 86 cm high
#   Tunnel           411 cm forward, 251 cm right, 74-122 cm high
#   Small cube       411 cm forward, 251 cm right, 33 cm tall
#  Fly-through directions: red arch, green keyhole, mini 1 and yellow keyhole: forward.
#  Blue arch: right. Mini 2: left. Mini 3: back toward the start. Tunnel: top to bottom.
#
#  Scoring: takeoff 5 · arches 5 · green 10 · yellow 20 · large cube 25 · each mini keyhole 15
#           spiral bonus (1→2→3 in a row) 10 · tunnel 15 · land: pad 5 / cube 10 / bullseye 15
# ────────────────────────────────────────────────────────────────────────
from codrone_edu.drone import *

drone = Drone()
drone.pair()
drone.takeoff()

# your mission here

drone.land()
drone.close()
