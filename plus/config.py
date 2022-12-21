import json
import os
import subprocess
import sys

from .constants import SUPPORTED_GAME_LANGS

config = {}
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except:
    pass

config_changed = False

GAME_LANG = config.get("game_lang")
while not GAME_LANG or GAME_LANG not in SUPPORTED_GAME_LANGS:
    GAME_LANG = input(f"Please input your game language (Supported: {','.join(SUPPORTED_GAME_LANGS)}): ")
    config["game_lang"] = GAME_LANG
    config_changed = True

class RecordOptions:
    def __init__(self, config):
        self.command = config["command"]
        self.returns_json = config.get("returns_json")
        if type(self.returns_json) is not bool:
            raise Exception("returns_json must be boolean")
    def create(self):
        return subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE if self.returns_json else sys.stderr,
            stderr=sys.stderr,
            shell=type(self.command) is str
        )

RECORD_OPTIONS = config.get("record")
if not RECORD_OPTIONS:
    print("[NOTE] Recording is disabled.", file=sys.stderr)
    RECORD_OPTIONS = None
else:
    print("[NOTE] Recording is enabled.", file=sys.stderr)
    RECORD_OPTIONS = RecordOptions(RECORD_OPTIONS)

if config_changed:
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

_upload_mode = os.environ.get("S3SPLUS_UPLOAD_MODE", "").lower()
if _upload_mode == "test":
    UPLOAD_MODE = "test"
elif _upload_mode == "enable":
    UPLOAD_MODE = "enable"
else:
    print("You should set S3SPLUS_UPLOAD_MODE environment to 'test' or 'enable'")
    exit(1)