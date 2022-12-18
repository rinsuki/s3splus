import datetime
from enum import Enum
import json
import cv2
import numpy
import os
import sys
import re

cap = cv2.VideoCapture(sys.argv[1] if re.match(r"^-?[0-9]+$", sys.argv[1]) is None else int(sys.argv[1]))
if not cap.isOpened():
    raise Exception("cant open specified movie file")

GAME_LANG = "ja"

class Mask:
    def __init__(self, name: str):
        self.name = name
        if os.path.exists(f"masks/{GAME_LANG}/{name}.png"):
            self.mask = cv2.imread(f"masks/{GAME_LANG}/{name}.png", cv2.IMREAD_GRAYSCALE)
            with open(f"masks/{GAME_LANG}/{name}.json", "r") as f:
                self.info = json.load(f)
        else:
            self.mask = cv2.imread(f"masks/und/{name}.png", cv2.IMREAD_GRAYSCALE)
            with open(f"masks/und/{name}.json", "r") as f:
                self.info = json.load(f)
        self.x = self.info["x"]
        self.y = self.info["y"]
        # remove black border from mask image and store as mask_min
        # e.g.
        # 000000000
        # 000000000
        # 000101000
        # 000010000
        # 000000000
        # -> x=3, y=2, w=3, h=2
        # first, find first non-zero pixel from left-top
        # then, find first non-zero pixel from right-bottom
        # then, crop image
        # then, store as mask_min
        self.mask_min = self.mask
        for y in range(self.mask.shape[0]):
            if numpy.count_nonzero(self.mask[y]) > 0:
                self.min_y = y + self.y
                break
        for x in range(self.mask.shape[1]):
            if self.mask[:, x].any():
                self.min_x = x + self.x
                break
        if self.min_x is None:
            raise Exception("mask image is empty")
        for y in range(self.mask.shape[0]-1, -1, -1):
            if numpy.count_nonzero(self.mask[y]) > 0:
                self.max_y = y + self.y
                break
        for x in range(self.mask.shape[1]-1, -1, -1):
            if self.mask[:, x].any():
                self.max_x = x + self.x
                break
        if self.max_x is None:
            raise Exception("mask image is empty")
        self.mask_min = self.mask[self.min_y-self.y:self.max_y-self.y+1, self.min_x-self.x:self.max_x-self.x+1]
        print(self.mask_min.size, (self.max_x-self.min_x+1)*(self.max_y-self.min_y+1))
        if self.mask_min.size == 0:
            raise Exception("mask image is empty")
    def check(self, img: cv2.Mat, sikii = 0.99):
        img_crop_min = img[self.min_y:self.max_y+1, self.min_x:self.max_x+1]
        found = numpy.count_nonzero(img_crop_min == self.mask_min)
        found /= self.mask_min.size
        # print("found_min", found)
        if found < sikii:
            return False
        img_crop = img[self.y:self.y+self.mask.shape[0], self.x:self.x+self.mask.shape[1]]
        found = numpy.count_nonzero(img_crop == self.mask)
        found /= self.mask.size
        # print("found_ful", found)
        return found > sikii

class State(Enum):
    UNKNOWN = 0
    BATTLE_LOBBY = 100
    BATTLE_LOBBY_MATCHING = 150
    BATTLE_LOBBY_MATCHED = 190
    BATTLE_INGAME_INTRO = 200
    BATTLE_INGAME = 210
    BATTLE_RESULT_PRE_FULLMAP = 300
    BATTLE_RESULT = 310
    BATTLE_RESULT_PROFILE = 350
    BATTLE_RESULT_SCOREBOARD = 390

class Rule(Enum):
    NAWABARI = 100
    AREA = 200
    YAGURA = 300
    HOKO = 400
    ASARI = 500

BATTLE_LOBBY_MATCHING_PREFIX = Mask("battle_lobby_matching_prefix")
BATTLE_LOBBY_MATCHED = Mask("battle_lobby_matched")
BATTLE_INTRO_TITLE = Mask("battle_intro_title")
BATTLE_RESULT_LOSE = Mask("battle_result_lose")
BATTLE_RESULT_WIN = Mask("battle_result_win")
BATTLE_MAP_ICON = Mask("battle_map_icon")
BATTLE_RESULT_MEDAL_HEADER = Mask("battle_result_medal_header")
BATTLE_INGAME_TIME_COLON = Mask("battle_ingame_time_colon")
BATTLE_INGAME_MUSIC_HEADER = Mask("battle_ingame_music_header")
BATTLE_RESULT_SCOREBOARD_ABUTTON = Mask("battle_result_scoreboard_abutton")
BATTLE_RESULT_SCOREBOARD_WINP = Mask("battle_result_scoreboard_winp")
BATTLE_INTRO_RULE_NAWABARI = Mask("battle_intro_rule_nawabari")
BATTLE_INTRO_RULE_AREA = Mask("battle_intro_rule_area")
BATTLE_INTRO_RULE_YAGURA = Mask("battle_intro_rule_yagura")
BATTLE_INTRO_RULE_HOKO = Mask("battle_intro_rule_hoko")
BATTLE_INTRO_RULE_ASARI = Mask("battle_intro_rule_asari")

current_state = State.UNKNOWN
current_state_frames = 0

def change_current_state(state: State):
    global current_state
    global current_state_frames
    if current_state != state:
        print(f"state changed: {current_state} -> {state}")
        current_state = state
        current_state_frames = 0
        return True
    else:
        current_state_frames += 1
        return False
i = 0

class MusicTitleMaskStore:
    def __init__(self):
        self.mask = numpy.zeros(shape=(1080-BATTLE_INGAME_MUSIC_HEADER.y, 1920))
        self.count = 0
        self.oldx = 0
    def add(self, mask: cv2.Mat, x: int):
        if x != self.oldx:
            self.oldx = x
            self.count = 0
            return
        self.count += 1
        if self.count < 10:
            # x座標が不安定な間は無視する
            return
        # (old + new) / 2
        self.mask = (self.mask + self.mask + mask) / 3
    def save(self):
        if self.count < 10:
            print("failed to detect music title")
            return
        cv2.imwrite(f"{current_battle_dir()}/music-title.png", self.mask[:, self.oldx:], [cv2.IMWRITE_PNG_COMPRESSION, 9])
        print("image saved")


current_music_title_mask_store = None

def generate_battle_id():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

current_battle_id = generate_battle_id() + "-missingstart"

def current_battle_dir():
    return "battles/" + current_battle_id + "/"

def set_current_battle_id(battle_id: str):
    global current_battle_id
    current_battle_id = battle_id
    os.makedirs(current_battle_dir(), exist_ok=True)

while True:
    ret, frame = cap.read(cv2.IMREAD_GRAYSCALE)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if ret:
        ret2, frame2 = cv2.threshold(gray, 0xE0, 255, cv2.THRESH_BINARY)
        # lobby
        if BATTLE_LOBBY_MATCHING_PREFIX.check(frame2):
            if change_current_state(State.BATTLE_LOBBY_MATCHING):
                print("matching...")
        if BATTLE_LOBBY_MATCHED.check(frame2):
            if change_current_state(State.BATTLE_LOBBY_MATCHED):
                print("matched!")
                set_current_battle_id(generate_battle_id())
        # ingame
        if BATTLE_INTRO_TITLE.check(frame2):
            rule = None
            if BATTLE_INTRO_RULE_NAWABARI.check(frame2):
                rule = Rule.NAWABARI
            elif BATTLE_INTRO_RULE_AREA.check(frame2):
                rule = Rule.AREA
            elif BATTLE_INTRO_RULE_YAGURA.check(frame2):
                rule = Rule.YAGURA
            elif BATTLE_INTRO_RULE_HOKO.check(frame2):
                rule = Rule.HOKO
            elif BATTLE_INTRO_RULE_ASARI.check(frame2):
                rule = Rule.ASARI
            if rule is not None:
                if change_current_state(State.BATTLE_INGAME_INTRO):
                    print("intro! rule=", rule)
                    with open(f"{current_battle_dir()}/rule.txt", "w") as f:
                        f.write(rule.name)
            else:
                print("failed to detect rule")
            if current_state_frames == 10:
                cv2.imwrite(f"{current_battle_dir()}/intro.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_INGAME_TIME_COLON.check(frame2):
            if change_current_state(State.BATTLE_INGAME):
                print("ingame!")
                current_music_title_mask_store = MusicTitleMaskStore()
            if current_music_title_mask_store is not None:
                if current_state_frames < 600:
                    # music title check
                    # slice bottom part of screen
                    img_crop = frame2[BATTLE_INGAME_MUSIC_HEADER.y:, :]
                    # find music title
                    result = cv2.matchTemplate(img_crop, BATTLE_INGAME_MUSIC_HEADER.mask, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    if max_val > 0.9:
                        print(max_val, max_loc)
                        current_music_title_mask_store.add(img_crop, max_loc[0])
                else:
                    print("finish detect music title")
                    current_music_title_mask_store.save()
                    current_music_title_mask_store = None
        elif current_state == State.BATTLE_INGAME and current_state_frames > 600 and BATTLE_MAP_ICON.check(frame2, 0.9):
            # result - finish map
            if change_current_state(State.BATTLE_RESULT_PRE_FULLMAP):
                print("result-map!")
                cv2.imwrite(f"{current_battle_dir()}/result-map.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        # result
        if BATTLE_RESULT_WIN.check(frame2):
            if change_current_state(State.BATTLE_RESULT):
                print("result-win!")
            if current_state_frames == 30:
                cv2.imwrite(f"{current_battle_dir()}/result.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_RESULT_LOSE.check(frame2):
            if change_current_state(State.BATTLE_RESULT):
                print("result-lose!")
            if current_state_frames == 30:
                cv2.imwrite(f"{current_battle_dir()}/result.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_RESULT_MEDAL_HEADER.check(frame2):
            if change_current_state(State.BATTLE_RESULT_PROFILE):
                print("result-profile!")
            if current_state_frames == 30:
                cv2.imwrite(f"{current_battle_dir()}/result_profile.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_RESULT_SCOREBOARD_ABUTTON.check(frame2) and BATTLE_RESULT_SCOREBOARD_WINP.check(frame2, 0.9):
            if change_current_state(State.BATTLE_RESULT_SCOREBOARD):
                print("result-scoreboard!")
            if current_state_frames == 30:
                cv2.imwrite(f"{current_battle_dir()}/result_scoreboard.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        cv2.imshow("frame", frame2)
        i += 1
        if i % 2 == 0:
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break