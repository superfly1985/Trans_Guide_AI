# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "/root/Trans_Guide_AI")

from modules.tm_db import TMDatabase

tm = TMDatabase("./data/tm.db", "./data/chroma_db")
s = tm.get_stats()
print(s)
