import datetime
from enum import Enum
import json
import os
import signal
import subprocess
import sys
import threading
import cv2
import numpy

from plus.config import RECORD_OPTIONS

from ..mask.music import MusicTitleMaskStore

from ..constants import Rule
from ..mask.images import *

class State(Enum):
    UNKNOWN = 0
    ERROR_SCHEDULE_REFRESH = -100
    BATTLE_LOBBY = 100
    BATTLE_LOBBY_MATCHING = 150
    BATTLE_LOBBY_MATCHED = 190
    BATTLE_INGAME_INTRO = 200
    BATTLE_INGAME = 210
    BATTLE_RESULT_PRE_FULLMAP = 300
    BATTLE_RESULT = 310
    BATTLE_RESULT_PROFILE = 350
    BATTLE_RESULT_SCOREBOARD = 390
    BATTLE_RESULT_BANKARA_CHALLENGE_FINISH = 391

class BattleDetector:
    def __init__(self):
        self.current_state = State.UNKNOWN
        self.current_state_frames = 0
        self.change_state_was_called = False
        self.prepare_next_battle("-startmissing")
        self.recording = None
        self.finalizing = None
    
    def change_state(self, state: State):
        if self.current_state != state:
            print(f"state changed: {self.current_state} -> {state}")
            self.current_state = state
            self.current_state_frames = 0
            return True
        self.current_state_frames += 1
        self.change_state_was_called = True
        return False
    
    def finalize_if_need(self):
        if self.can_finalize:
            print("start finalize")
            if self.finalizing is not None:
                self.finalizing.join()
            current_battle_dir = self.current_battle_dir()
            self.finalizing = threading.Thread(target=self._finalize_another_thread, args=(current_battle_dir,))
            self.finalizing.run()
            self.can_finalize = False
    def _finalize_another_thread(self, battle_dir: str):
        print("finalizing on another thread...")
        recording_json = None
        if self.recording is not None:
            self.recording.send_signal(signal.SIGINT)
            stdout_text, _ = self.recording.communicate()
            print(stdout_text)
            recording_json = json.loads(stdout_text)
            print("got recording response!")
        subprocess.Popen(["python3", "s3swrapper.py"], stdout=sys.stdout, stderr=sys.stderr, env={
            **os.environ,
            "S3SPLUS_BATTLE_DIR": battle_dir,
            "S3SPLUS_RECORDING_JSON": json.dumps(recording_json),
        })
        self.finalizing = None

    def prepare_next_battle(self, suffix: str = ""):
        self.current_battle_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + suffix
        print("prepare next battle", self.current_battle_id)
        self._current_battle_dir = None
        self.current_music_title_mask_store = None
        self.can_finalize = False
    
    def start_recording(self):
        if not RECORD_OPTIONS:
            return
        self.recording = RECORD_OPTIONS.create()
    
    def current_battle_dir(self):
        if self._current_battle_dir is None:
            dir = f"battles/{self.current_battle_id}/"
            os.makedirs(dir)
            self._current_battle_dir = dir
        return self._current_battle_dir

    def process_frame(self, frame: numpy.ndarray):
        frameGray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, frameBW = cv2.threshold(frameGray, 0xE0, 255, cv2.THRESH_BINARY)
        # lobby
        if BATTLE_LOBBY_MATCHING_PREFIX.check(frameBW):
            if (self.current_state != State.BATTLE_RESULT_SCOREBOARD or self.current_state_frames > 30) and self.change_state(State.BATTLE_LOBBY_MATCHING):
                print("matching...")
        if BATTLE_LOBBY_MATCHED.check(frameBW):
            if self.change_state(State.BATTLE_LOBBY_MATCHED):
                print("matched!")
                self.finalize_if_need()
                self.prepare_next_battle()
                self.start_recording()
        if ERROR_SCHEDULE_REFRESH.check(frameBW):
            if self.change_state(State.ERROR_SCHEDULE_REFRESH):
                print("schedule refresh!")
                self.finalize_if_need()
        # ingame
        if BATTLE_INTRO_TITLE.check(frameBW):
            rule = None
            if BATTLE_INTRO_RULE_NAWABARI.check(frameBW):
                rule = Rule.NAWABARI
            elif BATTLE_INTRO_RULE_AREA.check(frameBW):
                rule = Rule.AREA
            elif BATTLE_INTRO_RULE_YAGURA.check(frameBW):
                rule = Rule.YAGURA
            elif BATTLE_INTRO_RULE_HOKO.check(frameBW):
                rule = Rule.HOKO
            elif BATTLE_INTRO_RULE_ASARI.check(frameBW):
                rule = Rule.ASARI
            if rule is not None:
                if self.change_state(State.BATTLE_INGAME_INTRO):
                    print("intro! rule=", rule)
                    with open(f"{self.current_battle_dir()}/rule.txt", "w") as f:
                        f.write(rule.name)
            else:
                print("failed to detect rule")
            if self.current_state_frames == 20:
                cv2.imwrite(f"{self.current_battle_dir()}/intro.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_INGAME_TIME_COLON.check(frameBW):
            if self.change_state(State.BATTLE_INGAME):
                print("ingame!")
                self.current_music_title_mask_store = MusicTitleMaskStore()
            if self.current_music_title_mask_store is not None:
                if self.current_state_frames < 600:
                    # music title check
                    # slice bottom part of screen
                    img_crop = frameBW[BATTLE_INGAME_MUSIC_HEADER.y:, :]
                    # find music title
                    result = cv2.matchTemplate(img_crop, BATTLE_INGAME_MUSIC_HEADER.mask, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    if max_val > 0.9:
                        print(max_val, max_loc)
                        self.current_music_title_mask_store.add(img_crop, max_loc[0])
                else:
                    print("finish detect music title")
                    self.current_music_title_mask_store.save(dir=self.current_battle_dir())
                    self.current_music_title_mask_store = None
        elif self.current_state == State.BATTLE_INGAME and self.current_state_frames > 600 and BATTLE_MAP_ICON.check(frameBW, 0.9):
            # result - finish map
            # if change_state(State.BATTLE_RESULT_PRE_FULLMAP):
            #     print("result-map!")
            #     cv2.imwrite(f"{self.current_battle_dir()}/result-map.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
            pass
        # result
        if BATTLE_RESULT_WIN.check(frameBW):
            if self.change_state(State.BATTLE_RESULT):
                print("result-win!")
            if self.current_state_frames == 30:
                cv2.imwrite(f"{self.current_battle_dir()}/result.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_RESULT_LOSE.check(frameBW):
            if self.change_state(State.BATTLE_RESULT):
                print("result-lose!")
            if self.current_state_frames == 30:
                cv2.imwrite(f"{self.current_battle_dir()}/result.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if BATTLE_RESULT_MEDAL_HEADER.check(frameBW):
            if self.change_state(State.BATTLE_RESULT_PROFILE):
                print("result-profile!")
            if self.current_state_frames == 30:
                cv2.imwrite(f"{self.current_battle_dir()}/result_profile.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                self.can_finalize = True
        if BATTLE_RESULT_SCOREBOARD_ABUTTON.check(frameBW) and BATTLE_RESULT_SCOREBOARD_WINP.check(frameBW, 0.9):
            if self.change_state(State.BATTLE_RESULT_SCOREBOARD):
                print("result-scoreboard!")
            if self.current_state_frames == 30:
                cv2.imwrite(f"{self.current_battle_dir()}/result_scoreboard.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                self.finalize_if_need()
        if BATTLE_RESULT_BANKARA_CHALLENGE_FINISH_TITLE.check(frameBW) and BATTLE_RESULT_BANKARA_CHALLENGE_FINISH_ABUTTON.check(frameBW):
            if self.change_state(State.BATTLE_RESULT_BANKARA_CHALLENGE_FINISH):
                print("result-bankara-challenge-finish!")
                cv2.imwrite(f"{self.current_battle_dir()}/result_bankara_challenge_finish.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])
                self.finalize_if_need()