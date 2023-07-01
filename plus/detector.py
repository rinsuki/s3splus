import datetime
from enum import Enum
import json
import os
import signal
import subprocess
import sys
import threading
import time
import traceback
import cv2
import numpy

from .config import get_record_options

from .mask.music import MusicTitleMaskStore

from .constants import Rule
from .mask.images import *

class GameMode(Enum):
    UNKNOWN = 0
    BATTLE = 1
    SALMON = 2

    def is_valid(self):
        return self != GameMode.UNKNOWN

Y_DIFF_EVENT_MODE_RULE_DESC = 73

class State(Enum):
    UNKNOWN = 0
    ERROR_SCHEDULE_REFRESH = -100
    ERROR_SERVER_MAINTENANCE_SOON = -200
    LOBBY_MATCHING = 9000
    RESULT_PLEASE_WAIT = 9900

    BATTLE_LOBBY = 10100
    BATTLE_LOBBY_MATCHED = 10190
    BATTLE_INGAME_INTRO = 10200
    BATTLE_INGAME_INTRO_EST_POWER = 10205
    BATTLE_INGAME = 10210
    BATTLE_ERROR_NO_GAME_BY_DISCONNECT = 10290
    BATTLE_RESULT_PRE_FULLMAP = 10300
    BATTLE_RESULT = 10310
    BATTLE_RESULT_PROFILE = 10350
    BATTLE_RESULT_SCOREBOARD = 10390
    BATTLE_RESULT_BANKARA_CHALLENGE_FINISH = 10391

    SALMON_LOBBY = 20100
    SALMON_LOBBY_MATCHED = 20190
    SALMON_INGAME_INTRO = 20200
    SALMON_INGAME = 20210
    SALMON_RESULT_WAVES = 20300
    SALMON_RESULT_REACTION = 20310
    SALMON_RESULT_PLAYERLIST = 20350
    SALMON_RESULT_RATE_DIFF = 20355
    SALMON_RESULT_POINT_DESC = 20360
    SALMON_RESULT_CURRENT_POINTS = 20370

    def mode(self):
        if self.value >= 10000 and self.value < 20000:
            return GameMode.BATTLE
        elif self.value >= 20000 and self.value < 30000:
            return GameMode.SALMON
        else:
            return GameMode.UNKNOWN

class TimerGroup:
    def __init__(self):
        self.timers = []
    def new(tg, name: str):
        class Timer:
            def __init__(self, name: str):
                self.name = name
                self.start = time.time()
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_value, traceback):
                tg.timers.append((self.name, time.time() - self.start))
        return Timer(name)
    def print(self):
        # print as X.XXXms format
        res = ", ".join([f"{name}: {t * 1000:.2f}ms" for name, t in self.timers])
        print(res)

class Detector:
    def __init__(self):
        self.current_state = State.UNKNOWN
        self.last_valid_mode = GameMode.UNKNOWN
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
            if state.mode().is_valid():
                self.last_valid_mode = state.mode()
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
            self.finalizing = threading.Thread(target=self._finalize_another_thread, args=(current_battle_dir,self.last_valid_mode == GameMode.SALMON))
            self.finalizing.run()
            self.can_finalize = False
    def _finalize_another_thread(self, battle_dir: str, is_salmon: bool):
        print("finalizing on another thread...")
        recording_json = None
        if self.recording is not None:
            self.recording.send_signal(signal.SIGINT)
            stdout_text, _ = self.recording.communicate()
            print(stdout_text)
            try:
                recording_json = json.loads(stdout_text)
                print("got recording response!")
            except:
                print("failed to parse recording response")
                traceback.print_exc()
        subprocess.Popen(["python3", "s3swrapper.py"], stdout=sys.stdout, stderr=sys.stderr, env={
            **os.environ,
            "S3SPLUS_BATTLE_DIR": battle_dir,
            "S3SPLUS_RECORDING_JSON": json.dumps(recording_json),
            "S3SPLUS_IS_SALMON": "YES" if is_salmon else "NO",
        })
        self.finalizing = None

    def prepare_next_battle(self, suffix: str = ""):
        self.current_battle_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + suffix
        print("prepare next battle", self.current_battle_id)
        self._current_battle_dir = None
        self.current_music_title_mask_store = None
        self.can_finalize = False
    
    def start_recording(self):
        ro = get_record_options()
        if ro is None:
            return
        self.recording = ro.create()
    
    def current_battle_dir(self):
        if self._current_battle_dir is None:
            dir = f"battles/{self.current_battle_id}/"
            os.makedirs(dir)
            self._current_battle_dir = dir
        return self._current_battle_dir

    def process_frame(self, frame: numpy.ndarray):
        tg = TimerGroup()
        with tg.new("frame_gray"):
            frameGray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        with tg.new("frame_bw"):
            _, frameBW = cv2.threshold(frameGray, 0xE0, 255, cv2.THRESH_BINARY)
        # lobby
        with tg.new("check_shared"):
            if SHARAED_LOBBY_MATCHING_PREFIX.check(frameBW):
                if (self.current_state != State.BATTLE_RESULT_SCOREBOARD or self.current_state_frames > 30) and self.change_state(State.LOBBY_MATCHING):
                    print("matching...")
            if ERROR_SCHEDULE_REFRESH.check(frameBW):
                if self.change_state(State.ERROR_SCHEDULE_REFRESH):
                    print("schedule refresh!")
                    self.finalize_if_need()
            if SHARED_RESULT_PLEASE_WAIT.check(frameBW):
                if self.change_state(State.RESULT_PLEASE_WAIT):
                    print("please wait screen after finished")
                    self.finalize_if_need()
            if ERROR_SERVER_MAINTENANCE_SOON.check(frameBW):
                if self.change_state(State.ERROR_SERVER_MAINTENANCE_SOON):
                    print("server maintenance soon")
                    self.finalize_if_need()
        with tg.new("check_battle_always"):
            self.process_game_battle_always(frame, frameBW)
        if self.last_valid_mode != GameMode.SALMON:
            with tg.new("check_battle"):
                self.process_game_battle(frame, frameBW)
        with tg.new("check_salmon_always"):
            self.process_game_salmon_always(frame, frameBW)
        if self.last_valid_mode != GameMode.BATTLE:
            with tg.new("check_salmon"):
                self.process_game_salmon(frame, frameBW)
        # tg.print()
    
    def process_game_battle_always(self, frame: numpy.ndarray, frameBW: numpy.ndarray):
        if BATTLE_LOBBY_MATCHED.check(frameBW):
            if self.change_state(State.BATTLE_LOBBY_MATCHED):
                print("matched!")
                self.finalize_if_need()
                self.prepare_next_battle()
                self.start_recording()
        # ingame
        if BATTLE_INTRO_TITLE.check(frameBW) or BATTLE_INTRO_TITLE_TRICOLOR.check(frameBW):
            rule = None
            if BATTLE_INTRO_RULE_NAWABARI.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC):
                rule = Rule.NAWABARI
            elif BATTLE_INTRO_RULE_AREA.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC):
                rule = Rule.AREA
            elif BATTLE_INTRO_RULE_YAGURA.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC):
                rule = Rule.YAGURA
            elif BATTLE_INTRO_RULE_HOKO.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC):
                rule = Rule.HOKO
            elif BATTLE_INTRO_RULE_ASARI.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC):
                rule = Rule.ASARI
            elif BATTLE_INTRO_RULE_TRICOLOR_GUARD.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC) or BATTLE_INTRO_RULE_TRICOLOR_ATTACK.check_with_alternative_relative_y_offset(frameBW, Y_DIFF_EVENT_MODE_RULE_DESC):
                rule = Rule.TRICOLOR
            if rule is not None:
                if self.change_state(State.BATTLE_INGAME_INTRO):
                    print("intro! rule=", rule)
                    with open(f"{self.current_battle_dir()}/rule.txt", "w") as f:
                        f.write(rule.name)
            else:
                print("failed to detect rule")
            if self.current_state_frames == 20:
                cv2.imwrite(f"{self.current_battle_dir()}/intro.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])

    def process_game_battle(self, frame: numpy.ndarray, frameBW: numpy.ndarray):
        if BATTLE_INTRO_EST_POWER.check(frameBW):
            if self.change_state(State.BATTLE_INGAME_INTRO_EST_POWER):
                print("est power")
                # save
                cv2.imwrite(f"{self.current_battle_dir()}/intro_est_power.png", frameBW, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        if self.current_state != State.BATTLE_ERROR_NO_GAME_BY_DISCONNECT and (BATTLE_INGAME_TIME_COLON.check(frameBW) or BATTLE_INGAME_TIME_COLON_TRICOLOR.check(frameBW, 0.95)):
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
        if ERROR_NO_GAME_BY_DISCONNECT.check(frameBW):
            if self.change_state(State.BATTLE_ERROR_NO_GAME_BY_DISCONNECT):
                print("error-no-game-by-disconnect!")
                self.can_finalize = True
        if BATTLE_RESULT_SCOREBOARD_ABUTTON.check(frameBW) and (BATTLE_RESULT_SCOREBOARD_WINP.check(frameBW, 0.9) or BATTLE_RESULT_SCOREBOARD_WINP_TRICOLOR.check(frameBW, 0.9) or BATTLE_RESULT_SCOREBOARD_NO_GAME.check(frameBW)):
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

    def process_game_salmon_always(self, frame: numpy.ndarray, frameBW: numpy.ndarray):
        if SALMON_LOBBY_MATCHED.check(frameBW):
            if self.change_state(State.SALMON_LOBBY_MATCHED):
                print("salmon-matched!")
                self.finalize_if_need()
                self.prepare_next_battle("-salmon")
                self.start_recording()
        if SALMON_INGAME_WAVE_HEADER.check(frameBW):
            if self.change_state(State.SALMON_INGAME):
                print("salmon-ingame!")

    def process_game_salmon(self, frame: numpy.ndarray, frameBW: numpy.ndarray):
        if SALMON_RESULT_PLAYERLIST_1ST_DEAD_COUNT.check(frameBW):
            if self.change_state(State.SALMON_RESULT_PLAYERLIST):
                print("playerlist")
                self.can_finalize=True
        if SALMON_RESULT_POINT_DESC_HEADER.check(frameBW):
            if self.change_state(State.SALMON_RESULT_POINT_DESC):
                print("salmon-result!")
                self.finalize_if_need()
                