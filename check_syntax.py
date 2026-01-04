import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
try:
    from backend.strategy import SevenSplitStrategy
    print("Strategy import successful")
except Exception as e:
    import traceback
    traceback.print_exc()
