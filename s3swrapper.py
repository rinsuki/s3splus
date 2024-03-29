import json
import time
from PIL import Image
import requests
import os
from plus.config import UPLOAD_MODE
from s3sproxy import prepare_battle_result, headbutt, s3s, utils, prefetch_checks, write_config, CONFIG_DATA, check_statink_key, set_language, fetch_and_upload_single_result, iksm
from glob import glob
import functools
import json
import plus.utils
import msgpack
from pytesseract import pytesseract

GET_LATEST_BATTLE_ID = "73462e18d464acfdf7ac36bde08a1859aa2872a90ed0baed69c94864c20de046"
GET_LATEST_SALMON_ID = "bc8a3d48e91d5d695ef52d52ae466920670d4f4381cb288cd570dc8160250457"

def get_latest_splatnet_battle_id():
    res = requests.post(iksm.GRAPHQL_URL,
        data=utils.gen_graphql_body(GET_LATEST_BATTLE_ID),
        headers=headbutt()
    )
    res.raise_for_status()
    return res.json()["data"]["vsResult"]["historyGroups"]["nodes"][0]["historyDetails"]["nodes"][0]["id"]

def get_latest_splatnet_salmon_id():
    res = requests.post(iksm.GRAPHQL_URL,
        data=utils.gen_graphql_body(GET_LATEST_SALMON_ID),
        headers=headbutt()
    )
    return res.json()["data"]["coopResult"]["historyGroupsOnlyFirst"]["nodes"][0]["historyDetails"]["nodes"][0]["id"]

def pre_check():
    check_statink_key()
    set_language()
    # NOTE: this is hack for my own use-case
    #       originally i wrote small server that returns last token that used by app
    #       to use with rinsuki-lab/spl3historydumper
    #       normal people should use s3s's flapi method instead
    #       (...but if you are reading this source, you might not be normal people...?)
    if os.path.exists("historydumpertokens.json"):
        hdt = json.load(open("historydumpertokens.json"))
        while True:
            res = requests.post(hdt["http"]["url"], headers=hdt["http"]["headers"])
            if res.status_code == 503:
                print("Server Returns HTTP 503... Probably your token was expired?")
                time.sleep(1)
                continue
            break
        res.raise_for_status()
        res = res.json()
        CONFIG_DATA["gtoken"] = res["gtoken"]
        CONFIG_DATA["bullettoken"] = res["token"]
        CONFIG_DATA["session_token"] = "skip"
        write_config(CONFIG_DATA)
    prefetch_checks(printout=True)

pre_check()
print(get_latest_splatnet_battle_id())

recording_json = json.loads(os.environ.get("S3SPLUS_RECORDING_JSON", "null"))

latest_battle_id = glob("battles/20*")
latest_battle_id.sort()
latest_battle_id = os.environ.get("S3SPLUS_BATTLE_DIR") or latest_battle_id[-1]
print(latest_battle_id)

orig_msgpack_packb = msgpack.packb
def overrided_msgpack_packb(payload, *args, **kwargs):
    if payload["agent"] != "s3s":
        return orig_msgpack_packb(payload, *args, **kwargs)
    payload["agent"] = "s3splus"
    payload["agent_version"] = plus.utils.PLUS_VERSION
    if not is_salmon:
        if os.path.exists(f"{latest_battle_id}/result.png"):
            payload["image_judge"] = open(f"{latest_battle_id}/result.png", "rb").read()
        if os.path.exists(f"{latest_battle_id}/result_scoreboard.png"):
            payload["image_result"] = open(f"{latest_battle_id}/result_scoreboard.png", "rb").read()
        if os.path.exists(f"{latest_battle_id}/result_profile.png"):
            payload["image_gear"] = open(f"{latest_battle_id}/result_profile.png", "rb").read()
        if os.path.exists(f"{latest_battle_id}/intro_est_power.png"):
            payload["agent_variables"]["Plus: Rival Est Power (OCR)"] = pytesseract.image_to_string(f"{latest_battle_id}/intro_est_power.png", "eng+jpn").strip()
        with Image.open(latest_battle_id + "/music-title.png") as img:
            payload["agent_variables"]["Plus: Music Width"] = img.size[0]
            header_width = Image.open("masks/und/battle_ingame_music_header.png").size[0]
            img = img.crop((header_width, 0, img.size[0], img.size[1]))
            payload["agent_variables"]["Plus: Music OCRed Text"] = pytesseract.image_to_string(img, "eng+jpn").strip()
        try:
            rule_expected = open(latest_battle_id + "/rule.txt", "r").read().strip()
            if payload["rule"] != rule_expected.lower():
                raise Exception("invalid rule!!", payload["rule"], rule_expected)
        except:
            pass
    else:
        # TODO: add salmon additional info
        pass
    if recording_json is not None:
        payload["link_url"] = recording_json.get("url")
    # print(payload)
    return orig_msgpack_packb(payload, *args, **kwargs)
msgpack.packb = overrided_msgpack_packb

is_salmon = os.environ.get("S3SPLUS_IS_SALMON") == "YES"

if is_salmon:
    fetch_and_upload_single_result(get_latest_splatnet_salmon_id(), "job", False, UPLOAD_MODE != "enable")
else:
    fetch_and_upload_single_result(get_latest_splatnet_battle_id(), "battle", False, UPLOAD_MODE != "enable")
