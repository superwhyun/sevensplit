import sys
import os

# Set up path to mimic run.sh
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from backend.main import app
    print("Successfully imported app")
    
    print("Routes:")
    for route in app.routes:
        print(f"{route.path} {route.name}")
        
except Exception as e:
    print(f"Failed to import app: {e}")
    import traceback
    traceback.print_exc()
