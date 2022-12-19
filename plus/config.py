import json

from .constants import SUPPORTED_GAME_LANGS

config = {}
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except:
    pass

config_changed = False

GAME_LANG = config.get("GAME_LANG")
while not GAME_LANG or GAME_LANG not in SUPPORTED_GAME_LANGS:
    GAME_LANG = input(f"Please input your game language (Supported: {','.join(SUPPORTED_GAME_LANGS)}): ")
    config["GAME_LANG"] = GAME_LANG
    config_changed = True

if config_changed:
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

_upload_mode = config.get("S3SPLUS_UPLOAD_MODE", "").lower()
if _upload_mode == "test":
    UPLOAD_MODE = "test"
elif _upload_mode == "enable":
    UPLOAD_MODE = "enable"
else:
    print("You should set S3SPLUS_UPLOAD_MODE environment to 'test' or 'enable'")
    exit(1)