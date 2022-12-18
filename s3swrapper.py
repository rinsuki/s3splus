### s3s import hack
import sys
current_dir = sys.path[0]
print(current_dir)
sys.path.insert(0, current_dir + "/s3s")
from s3s import prepare_battle_result, headbutt
sys.path.remove(current_dir + "/s3s")
### s3s import hack end

from glob import glob

GET_LATEST_BATTLE_ID = "0329c535a32f914fd44251be1f489e24"

latest_battle_id = glob("battles/*")
latest_battle_id.sort()
latest_battle_id = latest_battle_id[-1]
print(latest_battle_id)