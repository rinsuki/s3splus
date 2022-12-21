import json
from PIL import Image
import requests
import os
from plus.config import UPLOAD_MODE
from s3sproxy import prepare_battle_result, headbutt, s3s, utils, prefetch_checks, write_config, CONFIG_DATA, check_statink_key, set_language, fetch_and_upload_single_result
from glob import glob
import functools
import json
import plusutils
import msgpack


GET_LATEST_BATTLE_ID = "0329c535a32f914fd44251be1f489e24"

def get_latest_splatnet_battle_id():
    res = requests.post(utils.GRAPHQL_URL,
        data=utils.gen_graphql_body(GET_LATEST_BATTLE_ID),
        headers=headbutt()
    )
    res.raise_for_status()
    return res.json()["data"]["vsResult"]["historyGroups"]["nodes"][0]["historyDetails"]["nodes"][0]["id"]

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
        res = requests.post(hdt["http"]["url"], headers=hdt["http"]["headers"])
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
    payload["image_judge"] = open(f"{latest_battle_id}/result.png", "rb").read()
    if os.path.exists(f"{latest_battle_id}/result_scoreboard.png"):
        payload["image_result"] = open(f"{latest_battle_id}/result_scoreboard.png", "rb").read()
    payload["image_gear"] = open(f"{latest_battle_id}/result_profile.png", "rb").read()
    payload["agent"] = "s3splus"
    payload["agent_version"] = plusutils.PLUS_VERSION
    with Image.open(latest_battle_id + "/music-title.png") as img:
        payload["agent_variables"]["Plus: Music Width"] = img.size[0]
        from pytesseract import pytesseract
        header_width = Image.open("masks/und/battle_ingame_music_header.png").size[0]
        img = img.crop((header_width, 0, img.size[0], img.size[1]))
        payload["agent_variables"]["Plus: Music OCRed Text"] = pytesseract.image_to_string(img, "eng+jpn").strip()
    rule_expected = open(latest_battle_id + "/rule.txt", "r").read().strip()
    if payload["rule"] != rule_expected.lower():
        raise Exception("invalid rule!!", payload["rule"], rule_expected)
    if recording_json is not None:
        payload["link_url"] = recording_json.get("url")
    # print(payload)
    return orig_msgpack_packb(payload, *args, **kwargs)
msgpack.packb = overrided_msgpack_packb

fetch_and_upload_single_result(get_latest_splatnet_battle_id(), "battle", False, UPLOAD_MODE != "enable")
