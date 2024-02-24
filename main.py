import datetime
from enum import Enum
import json
import subprocess
import cv2
import numpy
import os
import sys
import re

from plus.detector import Detector
from plus.config import force_disable_record
from plus.utils import PLUS_VERSION

print("Starting s3splus", PLUS_VERSION)

input_file = sys.argv[1] if re.match(r"^-?[0-9]+$", sys.argv[1]) is None else int(sys.argv[1])
cap = cv2.VideoCapture(input_file)
if type(input_file) is not int:
    print("[NOTE] Recording is disabled because input is recorded file", file=sys.stderr)
    force_disable_record()
if not cap.isOpened():
    raise Exception("cant open specified movie file")

detector = Detector()

i = 0

while True:
    ret, frame = cap.read(cv2.IMREAD_GRAYSCALE)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    if ret:
        wk = cv2.waitKey(1)
        detector.process_frame(frame)
        cv2.imshow("frame", frame)
        i += 1
        if i % 2 == 0:
            if wk & 0xFF == ord('q'):
                break
            if wk & 0xFF == ord('s'):
                cv2.imwrite(f"captures.{datetime.datetime.now().strftime('%Y%m%d.%H%M%S')}.png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 9])