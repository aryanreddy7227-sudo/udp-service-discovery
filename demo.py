#!/usr/bin/env python3
"""
One-command launcher for the main UDP service-discovery + SDN demo.

Run from the repository root:
  sudo env OSKEN_PYTHON="$HOME/osken-env/bin/python" python3 demo.py

The script builds the C programs, starts the OS-Ken controller, creates the
Mininet topology, starts the registry and both service agents, then opens the
Mininet CLI. Use "h4 ./client HTTP" or "h4 ./client FTP" in that CLI.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SDN_DIR = ROOT / "member2"
OSKEN_PYTHON = os.environ.get("OSKEN_PYTHON", str(Path.home() / "osken-env/bin/python"))
CONTROLLER_PORT = 6653

def require_file(path):
    if not path.is_file():
        raise SystemExit(f"Required file not found: {path}")

def main():
    if os.geteuid() != 0:
        raise SystemExit(
            'Mininet needs root. Run:\n'
            '  sudo env OSKEN_PYTHON="$HOME/osken-env/bin/python" python3 demo.py'
        )

    for name in ("registry.c", "server.c", "ftp_server.c", "client.c",
                 "common.h", "member2/sdn_topology.py",
                 "member2/run_sdn_controller.py", "member2/sdn_controller.py"):
        require_file(ROOT / name)

    if not Path(OSKEN_PYTHON).is_file():
        raise SystemExit(
            f"OS-Ken Python not found: {OSKEN_PYTHON}\n"
            'Create/install the environment or pass its path with OSKEN_PYTHON.'
        )

    print("[DEMO] Building C programs...", flush=True)
    subprocess.run(["make", "build"], cwd=ROOT, check=True)

    # Import Mininet only after checking the required environment.
    try:
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.cli import CLI
    except ImportError as exc:
        raise SystemExit(f"Mininet Python modules are unavailable: {exc}")

    sys.path.insert(0, str(SDN_DIR))
    from sdn_topology import SDNServiceTopo

    controller_log = open(ROOT / "controller-demo.log", "w")
    controller = subprocess.Popen(
        [OSKEN_PYTHON, str(SDN_DIR / "run_sdn_controller.py")],
        cwd=SDN_DIR,
        stdout=controller_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    net = None
    host_processes = []

    try:
        print("[DEMO] Starting OS-Ken controller...", flush=True)
        time.sleep(3)
        if controller.poll() is not None:
            raise RuntimeError(
                "OS-Ken controller exited early. Check controller-demo.log "
                "and confirm OS-Ken is installed in the selected environment."
            )

        topo = SDNServiceTopo()
        net = Mininet(
            topo=topo,
            controller=None,
            switch=OVSSwitch,
            autoSetMacs=True,
            build=True,
        )
        net.addController(
            "c0",
            controller=RemoteController,
            ip="127.0.0.1",
            port=CONTROLLER_PORT,
        )
        print("[DEMO] Starting Mininet network...", flush=True)
        net.start()
        time.sleep(3)

        h1, h2, h3, h4 = (net.get(name) for name in ("h1", "h2", "h3", "h4"))
        print("[DEMO] Starting UDP registry in h1...", flush=True)
        host_processes.append(h1.popen([str(ROOT / "registry")], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT))
        time.sleep(1)
        print("[DEMO] Starting HTTP agent in h2 and FTP agent in h3...", flush=True)
        host_processes.append(h2.popen([str(ROOT / "server")], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT))
        host_processes.append(h3.popen([str(ROOT / "ftp_server")], stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT))
        time.sleep(2)

        print("\n[DEMO] All main components have been started.")
        print("[DEMO] In the Mininet prompt, try:")
        print("       h4 ./client HTTP")
        print("       h4 ./client FTP")
        print("       pingall")
        print("       link s2 s3 down   (test backup path)")
        print("       link s2 s3 up")
        print("       exit              (stop the demo and clean up)\n", flush=True)
        CLI(net)

    except KeyboardInterrupt:
        print("\n[DEMO] Interrupt received; shutting down...", flush=True)
    finally:
        for proc in host_processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in host_processes:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if net is not None:
            net.stop()
        if controller.poll() is None:
            controller.terminate()
            try:
                controller.wait(timeout=3)
            except subprocess.TimeoutExpired:
                controller.kill()
        controller_log.close()
        print("[DEMO] Mininet, service processes and controller stopped.", flush=True)
        print("[DEMO] If stale Mininet state remains, run: sudo mn -c", flush=True)

if __name__ == "__main__":
    main()
