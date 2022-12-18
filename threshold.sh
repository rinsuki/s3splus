#!/bin/bash
ffmpeg -i "$1" -f lavfi -i color=0xE0E0E0:s=1920x1080 -f lavfi -i color=black:s=1920x1080 -f lavfi -i color=white:s=1920x1080 -lavfi threshold "$1.threshold.png"