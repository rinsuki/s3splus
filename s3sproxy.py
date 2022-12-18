### s3s import hack
import sys
current_dir = sys.path[0]
# print(current_dir)
sys.path.insert(0, current_dir + "/s3s")
from s3s import *
import s3s
sys.path.remove(current_dir + "/s3s")
### s3s import hack end