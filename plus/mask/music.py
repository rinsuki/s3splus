import numpy
import cv2
from .images import BATTLE_INGAME_MUSIC_HEADER

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
    def save(self, dir: str):
        if self.count < 10:
            print("failed to detect music title")
            return
        cv2.imwrite(f"{dir}/music-title.png", self.mask[:, self.oldx:], [cv2.IMWRITE_PNG_COMPRESSION, 9])
        print("image saved")

