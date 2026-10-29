from os_ken.base import app_manager
from os_ken.lib import hub


def main():
    manager = app_manager.AppManager.get_instance()

    manager.load_apps([
        "sdn_controller.py"
    ])

    contexts = manager.create_contexts()
    services = manager.instantiate_apps(**contexts)

    print("[CONTROLLER] SDN controller started.")

    try:
        hub.joinall(services)
    except KeyboardInterrupt:
        print("[CONTROLLER] Stopping controller...")
        manager.close()


if __name__ == "__main__":
    main()
