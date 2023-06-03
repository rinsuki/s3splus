import os
import json
import cv2
import numpy

from ..config import GAME_LANG

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
    def check(self, img: cv2.Mat, sikii: float = 0.99):
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
    def check_with_alternative_relative_y_offset(self, img: cv2.Mat, y: int, sikii: float = 0.99):
        if self.check(img, sikii):
            return True
        if self.check(img[y:img.shape[0], :], sikii):
            return True
        return False