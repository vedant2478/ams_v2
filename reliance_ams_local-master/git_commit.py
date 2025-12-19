# modified

import os
from datetime import datetime


os.system('git add -A')
os.system(f'git commit -a -m "final commit as per date {datetime.now().date()}')
os.system('git push -u origin master')