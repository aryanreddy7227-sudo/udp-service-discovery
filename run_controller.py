from os_ken.base import app_manager
import time

manager = app_manager.AppManager.get_instance()

manager.load_apps(["controller.py"])
manager.instantiate_apps()

print("[CONTROLLER] OS-Ken controller started.")

while True:
    time.sleep(1)
