import subprocess

try:
    PLUS_VERSION = subprocess.check_output(["git", "describe", "--dirty=+dirty", "--tags"]).decode('utf-8').strip()
except:
    print("WARNING: git not found, using \"unknown\" version")
    PLUS_VERSION = "unknown"

from s3sproxy import A_VERSION
PLUS_VERSION += " (s3s/" + A_VERSION + ")"
