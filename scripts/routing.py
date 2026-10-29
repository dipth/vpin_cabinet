"""Routed cable lengths for the harness sheets.

Every long run is described as a path of waypoints through the cabinet's cable
trays. Its length is the Manhattan distance along that path, plus 15 cm of
service slack at each end, rounded up to the next 0.1 m.

    python scripts/routing.py           # print the table
    python scripts/routing.py --apply   # also write the lengths into harness/*.yml

Coordinates are millimetres inside the cabinet: x from the front wall (0) to
the rear wall (1270), y from the left wall (0) to the right wall (585), z up
from the floor. Positions are estimates from Tukkari's drawings, the real-mech
add-on drawing and James' build; move a part here and re-run.

Short local leads (jumpers, button leads, splice tails) keep the lengths
written on their sheets.
"""

import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLACK_MM = 2 * 150

# --- Positions --------------------------------------------------------------------------------
P = {
    # real-mech board shelf (front) and flipper shelf (just behind it)
    "SDC": (110, 290, 310),
    "BUNNY1": (110, 110, 310),
    "BUNNY2": (110, 470, 310),
    "LAMP_SPLICE": (150, 290, 280),
    "AMP": (250, 290, 290),
    "SOUNDCARD": (250, 190, 290),
    "X_FLIP_L": (250, 60, 250),
    "X_FLIP_R": (250, 525, 250),
    "FLIP_SPLICE": (250, 290, 250),
    "INTERLOCK": (15, 220, 250),
    "PERSPEX_L": (110, 30, 380),
    "PERSPEX_R": (110, 555, 380),
    # bumper-row braces (underside)
    "X_BUMP_F": (610, 60, 360),
    "X_BUMP_R": (940, 60, 420),
    # floor toys and audio
    "GEAR": (850, 560, 150),     # upper right: right wall, in front of the 5 V supply
    "SHAKER_MOTOR": (450, 480, 60),
    "BST1": (420, 330, 20),
    "SUB": (330, 290, 20),
    "CHIMES": (470, 575, 220),
    "BELL_L": (1265, 70, 300),
    "BELL_S": (1265, 515, 300),
    # rear: power corner left (12 V + 24 V), right (5 V), PC in the middle
    # PSUs end ~8 cm short of the rear wall so their terminal wiring can bend;
    # fuse blocks sit in front of the left-hand PSUs, below the rear brace.
    "PSU12_DC": (1165, 25, 85),       # RSP-320-12, x 950-1165, z 20-135
    "PSU24_DC": (1170, 25, 230),      # RSP-500-24, x 940-1170, z 160-287
    "FB12": (850, 10, 85),            # 5026, 164 x 84 mm, x 768-932
    "FB24": (870, 10, 235),           # 5025, 124 x 84 mm, x 808-932
    "PSU5_DC": (1165, 560, 85),       # RSP-320-5, x 950-1165, z 20-135
    "FB5": (1060, 575, 235),          # 5026 above the PSU, x 978-1142, z 193-277
    "PC_IO": (1220, 290, 150),
    "FAN_HUB": (1110, 290, 250),
    "AMP_PSU": (1150, 120, 40),
    "DMD_PSU": (1240, 300, 15),
    "INLET": (1270, 520, 150),
    "COUPLER": (1245, 430, 15),
    "PE_BAR": (1245, 480, 15),
    # strip outlets, rear wall
    "SW1": (1255, 470, 60), "SW2": (1255, 120, 60), "SW3": (1255, 170, 60),
    "SW4": (1255, 220, 60), "SW5": (1255, 270, 60), "MASTER": (1255, 320, 60),
    "AO1": (1255, 360, 60), "AO2": (1255, 410, 60),
    # playfield, backboard, side rails
    "OLED_IN": (700, 450, 530),
    "P1": (1190, 95, 600), "P3": (1190, 255, 600), "P5": (1190, 415, 600),
    "P2": (1190, 175, 600), "P4": (1190, 335, 600), "P6": (1190, 495, 600),
    "FLASH_L": (1180, 40, 620), "FLASH_R": (1180, 545, 620),
    "SIDE_L_BACK": (1150, 15, 540), "SIDE_R_BACK": (1150, 570, 540),
    "SIDE_FRONT_L": (100, 15, 540), "SIDE_FRONT_R": (100, 570, 540),
    "EXC_TOP_L": (1080, 30, 520), "EXC_TOP_R": (1080, 555, 520),
    "EXC_BOT_L": (330, 30, 450), "EXC_BOT_R": (330, 555, 450),
    "THERM": (1150, 290, 520),
    # front
    "MXB_MAGNA_R": (30, 545, 300),
    "FAN_FRONT": (30, 290, 60),
    "PC_POWER_BTN": (15, 400, 0),
    # under-cab strip floor holes (rear corners)
    "UC_HOLE_R": (1240, 575, 0), "UC_HOLE_L": (1240, 10, 0),
    "UC_SPLICE": (1230, 575, 10),
    # backbox neck: LED/5 V on the right, toys/audio/video on the left
    "NECK_R": (1235, 520, 620), "NECK_L": (1235, 60, 620),
    "BG_IN": (1320, 350, 1000), "DMD_IN": (1310, 450, 780),
    "FAN_REAR_L": (1265, 210, 330), "FAN_REAR_R": (1265, 375, 330),
}

# --- Tray waypoints ---------------------------------------------------------------------------
# lane 1 mains: rear floor (x=1250). lane 2a 5 V + LED data: right-wall floor (y=575).
# lane 2b toy power: left-wall floor (y=10). lane 3 speakers/USB/video: centre floor
# (y=220, x 280-1050). Cross-cabinet runs use the brace undersides: front brace x=610
# z=360 (toy power), rear brace x=940 z=420 (5 V / LED).
def R(x, z=10):          # right tray
    return (x, 575, z)

def L(x, z=10):          # left tray
    return (x, 10, z)

def C(x):                # centre speaker tray
    return (x, 220, 10)

DROP_R = R(195)          # board shelf → right tray
DROP_L = L(195)          # board shelf → left tray
LEFT_UP = (1225, 10)     # climb point: the rear-left corner, behind the PSUs

PATHS = {
    # sheet 01 - mains
    "01/W_INLET": ["INLET", "COUPLER"],
    "01/W_PE_FEED": ["INLET", "PE_BAR"],
    "01/C_PSU_5V": ["SW1", (1250, 470, 10), (1250, 560, 10), "PSU5_DC"],
    "01/C_PSU_12V": ["SW2", (1250, 120, 10), (1250, 25, 10), "PSU12_DC"],
    "01/C_PSU_24V": ["SW3", (1250, 170, 10), (1250, 25, 10), "PSU24_DC"],
    "01/C_AMP": ["SW4", (1250, 220, 10), "AMP_PSU"],
    "01/C_AMP_DC": ["AMP_PSU", C(1050), C(280), "AMP"],
    "01/C_DMD_DC": ["DMD_PSU", (1235, 60, 10), "NECK_L", "DMD_IN"],
    # sheet 02 - USB and the PC power button
    "02/W_USB": ["PC_IO", C(1050), C(280), "SDC"],
    "02/L_PC_POWER": ["PC_IO", C(1050), C(280), (15, 400, 10), "PC_POWER_BTN"],
    # sheet 03 - 5 V LEDs
    "03/GND_REF": ["SDC", DROP_R, R(1120), "FB5"],
    "03/D_MX1": ["SDC", DROP_R, R(1190), R(1190, 600), "P1"],
    "03/D_MX2": ["SDC", DROP_R, R(1190), R(1190, 600), "P3"],
    "03/D_MX3": ["SDC", DROP_R, R(1190), R(1190, 600), "P5"],
    "03/D_MX4": ["SDC", DROP_R, R(940), R(940, 420), L(940, 420), L(1180, 420), "FLASH_L"],
    "03/D_MX5": ["SDC", DROP_R, R(1180), "FLASH_R"],
    "03/PW_P1": ["FB5", R(1190, 235), R(1190, 600), "P1"],
    "03/PW_P2": ["FB5", R(1190, 235), R(1190, 600), "P2"],
    "03/PW_P3": ["FB5", R(1190, 235), R(1190, 600), "P3"],
    "03/PW_P4": ["FB5", R(1190, 235), R(1190, 600), "P4"],
    "03/PW_P5": ["FB5", R(1190, 235), R(1190, 600), "P5"],
    "03/PW_P6": ["FB5", R(1190, 235), R(1190, 600), "P6"],
    "03/PW_ZONE_L": ["FB5", R(940, 235), R(940, 420), L(940, 420), L(1150, 420), "SIDE_L_BACK"],
    "03/PW_ZONE_R": ["FB5", R(1150, 235), "SIDE_R_BACK"],
    "03/PW_SIDE_L_FRONT": ["SIDE_L_BACK", "SIDE_FRONT_L"],
    "03/PW_SIDE_R_FRONT": ["SIDE_R_BACK", "SIDE_FRONT_R"],
    # sheet 04 - MX Buttons, under-cab, backbox
    "04/PW_MXB": ["FB5", R(1060), R(30), "MXB_MAGNA_R"],
    "04/PW_UC": ["FB5", R(1060), "UC_SPLICE"],
    "04/PW_UC_START": ["UC_SPLICE", "UC_HOLE_R"],
    "04/PW_UC_END": ["UC_SPLICE", R(940), R(940, 420), L(940, 420), L(940), L(1240), "UC_HOLE_L"],
    "04/D_MX7": ["SDC", DROP_R, R(1240), "UC_HOLE_R"],
    "04/PW_BB": ["FB5", R(1200, 235), R(1200, 620), "NECK_R"],
    "04/PW_BBR": ["FB5", R(1200, 235), R(1200, 620), "NECK_R"],
    "04/D_MX8": ["SDC", DROP_R, R(1235), (1235, 575, 620), "NECK_R"],
    # sheet 05 - toy power, BUNNYs, 12 V toys
    "05/PW_LOGIC_1": ["FB12", L(850), DROP_L, "BUNNY1"],
    "05/PW_LOGIC_2": ["FB12", L(850), DROP_L, (195, 470, 10), "BUNNY2"],
    "05/G_BUNNY_1": ["FB24", L(870), DROP_L, "BUNNY1"],
    "05/G_BUNNY_2": ["FB12", L(850), DROP_L, (195, 470, 10), "BUNNY2"],
    "05/PW_LAMPS": ["FB12", L(850), DROP_L, "LAMP_SPLICE"],
    "05/PW_GEAR": ["FB12", L(850), L(610), L(610, 360), (610, 560, 360), "GEAR"],
    "05/T_GEAR": ["BUNNY2", (195, 470, 10), DROP_L, L(610), L(610, 360), (610, 560, 360), "GEAR"],
    "05/PW_SHAKER": ["FB12", L(850), L(450), (450, 480, 10), "SHAKER_MOTOR"],
    "05/G_SHAKER_BUCK": ["FB12", L(850), L(450), (450, 480, 10), "SHAKER_MOTOR"],
    "05/T_SHAKER": ["BUNNY2", (195, 470, 10), (450, 470, 10), "SHAKER_MOTOR"],
    "05/PW_BB_TOYS": ["FB12", (1225, 10, 85), (1225, 10, 600), "NECK_L"],
    "05/T_BB_TOYS": ["BUNNY2", (195, 470, 10), DROP_L, L(1225), (1225, 10, 600), "NECK_L"],
    "05/PW_PERSPEX": ["FB12", L(850), DROP_L, "INTERLOCK"],
    "05/L_PERSPEX": ["INTERLOCK", "PERSPEX_L", "PERSPEX_R"],
    "05/G_PERSPEX": ["FB12", L(850), DROP_L, "PERSPEX_L"],
    "05/BOND_TOY": ["FB12", "FB24"],
    # sheet 06 - audio, video, USB
    "06/V_OLED": ["PC_IO", C(1050), C(700), "OLED_IN"],
    "06/V_BG": ["PC_IO", (1235, 60, 150), "NECK_L", "BG_IN"],
    "06/V_DMD": ["PC_IO", (1235, 60, 150), "NECK_L", "DMD_IN"],
    "06/U_SC": ["PC_IO", C(1050), C(280), "SOUNDCARD"],
    "06/S_EXC_TOP_L": ["AMP", C(280), C(1080), (1080, 30, 10), "EXC_TOP_L"],
    "06/S_EXC_TOP_R": ["AMP", C(280), C(1080), (1080, 555, 10), "EXC_TOP_R"],
    "06/S_EXC_BOT_L": ["AMP", C(330), (330, 30, 10), "EXC_BOT_L"],
    "06/S_EXC_BOT_R": ["AMP", C(330), (330, 555, 10), "EXC_BOT_R"],
    "06/S_BB_L": ["AMP", C(280), C(1050), (1235, 60, 10), "NECK_L"],
    "06/S_BB_R": ["AMP", C(280), C(1050), (1235, 60, 10), "NECK_L"],
    "06/S_SHAKER": ["AMP", C(420), "BST1"],
    "06/S_SUB": ["AMP", "SUB"],
    # sheet 07 - fans
    "07/X_FAN_1": ["FAN_HUB", C(1050), C(280), "FAN_FRONT"],
    "07/X_FAN_2": ["FAN_HUB", "FAN_REAR_L"],
    "07/X_FAN_3": ["FAN_HUB", "FAN_REAR_R"],
    # sheet 09 - coils
    "09/PW_FLIP": ["FB24", L(870), L(250), "FLIP_SPLICE"],
    "09/PW_SLING": ["FB24", L(870), L(250), "FLIP_SPLICE"],
    "09/PW_FLIP_L": ["FLIP_SPLICE", "X_FLIP_L"],
    "09/PW_FLIP_R": ["FLIP_SPLICE", "X_FLIP_R"],
    "09/PW_SLING_L": ["FLIP_SPLICE", "X_FLIP_L"],
    "09/PW_SLING_R": ["FLIP_SPLICE", "X_FLIP_R"],
    "09/R_FLIP_L": ["BUNNY1", "X_FLIP_L"],
    "09/R_FLIP_R": ["BUNNY1", "X_FLIP_R"],
    "09/PW_BUMP_F": ["FB24", L(870), L(610), L(610, 360), "X_BUMP_F"],
    "09/R_BUMP_F": ["BUNNY1", DROP_L, L(610), L(610, 360), "X_BUMP_F"],
    "09/PW_BUMP_R": ["FB24", L(940, 420), "X_BUMP_R"],
    "09/R_BUMP_R": ["BUNNY1", DROP_L, L(940), L(940, 420), "X_BUMP_R"],
    "09/PW_CHIMES": ["FB24", L(870), L(610), L(610, 360), (610, 575, 360), "CHIMES"],
    "09/R_CHIMES": ["BUNNY1", DROP_L, L(610), L(610, 360), (610, 575, 360), "CHIMES"],
    "09/PW_BELLS": ["FB24", (1225, 10, 235), (1225, 10, 300), (1265, 10, 300), "BELL_L"],
    "09/C_BELL_S": ["BELL_L", "BELL_S"],
    "09/R_BELLS": ["BUNNY1", DROP_L, L(1225), (1225, 10, 300), (1265, 10, 300), "BELL_L", "BELL_S"],
    "09/PW_KNOCKER": ["FB24", (1225, 10, 235), (1225, 10, 600), "NECK_L"],
    "09/R_KNOCKER": ["BUNNY1", DROP_L, L(1225), (1225, 10, 600), "NECK_L"],
}

# Cables whose length is the supplied cord's, not ours: print, don't apply.
REPORT_ONLY = {"01/C_DMD_DC"}


def pt(p):
    return P[p] if isinstance(p, str) else p


def manhattan(a, b):
    return sum(abs(i - j) for i, j in zip(a, b))


def length_m(path):
    pts = [pt(p) for p in path]
    mm = sum(manhattan(a, b) for a, b in zip(pts, pts[1:])) + SLACK_MM
    return math.ceil(round(mm / 100, 6)) / 10


def set_length(text, cable, metres):
    lines = text.split("\n")
    start = lines.index("cables:")
    end = next(i for i in range(start + 1, len(lines)) if lines[i] and not lines[i].startswith(" "))
    head = next((i for i in range(start, end) if re.match(rf"^  {re.escape(cable)}:(\s|$)", lines[i])), None)
    if head is None:
        raise KeyError(cable)
    block_end = next((i for i in range(head + 1, end) if re.match(r"^  \S", lines[i])), end)
    idx = next((i for i in range(head + 1, block_end) if lines[i].startswith("    length:")), None)
    new = f"    length: {metres:g}"
    if idx is None:
        lines.insert(head + 1, new)
    else:
        lines[idx] = new
    return "\n".join(lines)


def main():
    apply = "--apply" in sys.argv
    sheets = {p.name[:2]: p for p in (ROOT / "harness").glob("[0-9]*.yml")}
    texts = {k: p.read_text() for k, p in sheets.items()}
    for key, path in PATHS.items():
        sheet, cable = key.split("/")
        metres = length_m(path)
        flag = "  (supplied cord - check it reaches)" if key in REPORT_ONLY else ""
        print(f"{key:20s} {metres:4.1f} m{flag}")
        if apply and key not in REPORT_ONLY:
            texts[sheet] = set_length(texts[sheet], cable, metres)
    if apply:
        for k, p in sheets.items():
            p.write_text(texts[k])
        print("lengths written to harness/*.yml")


if __name__ == "__main__":
    main()
