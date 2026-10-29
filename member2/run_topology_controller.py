from oslo_config import cfg
from os_ken.base import app_manager
from os_ken.topology import switches
import time


CONF = cfg.CONF

CONF.set_override(
    'observe-links',
    True
)


def main():

    manager = app_manager.AppManager.get_instance()

    manager.load_apps([
        "topology_controller.py"
    ])

    manager.instantiate_apps()

    print("[CONTROLLER] Topology-aware SDN controller started.")
    print("[CONTROLLER] Link discovery enabled.")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
