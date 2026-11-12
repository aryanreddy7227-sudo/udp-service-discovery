#!/usr/bin/env python3
"""One-command launcher for the main UDP + SDN demo.
Run: sudo env OSKEN_PYTHON="$HOME/osken-env/bin/python" python3 demo.py
"""
import os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SDN = ROOT / "member2"
OSKEN_PYTHON = os.environ.get("OSKEN_PYTHON", str(Path.home() / "osken-env/bin/python"))

def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with: sudo env OSKEN_PYTHON="$HOME/osken-env/bin/python" python3 demo.py')
    for name in ("registry.c", "server.c", "ftp_server.c", "client.c", "common.h",
                 "member2/sdn_topology.py", "member2/run_sdn_controller.py", "member2/sdn_controller.py"):
        if not (ROOT / name).is_file():
            raise SystemExit(f"Missing required file: {name}")
    if not Path(OSKEN_PYTHON).is_file():
        raise SystemExit(f"OS-Ken Python not found: {OSKEN_PYTHON}")

    print("[DEMO] Compiling C programs...", flush=True)
    subprocess.run(["make", "build"], cwd=ROOT, check=True)
    try:
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.cli import CLI
    except ImportError as exc:
        raise SystemExit(f"Mininet Python modules unavailable: {exc}")

    sys.path.insert(0, str(SDN))
    from sdn_topology import SDNServiceTopo

    log_dir = ROOT / "demo-logs"
    log_dir.mkdir(exist_ok=True)
    controller_log = open(log_dir / "controller.log", "w")
    service_logs = []
    host_processes = []
    controller = subprocess.Popen(
        [OSKEN_PYTHON, str(SDN / "run_sdn_controller.py")],
        cwd=SDN, stdout=controller_log, stderr=subprocess.STDOUT
    )
    net = None
    try:
        print("[DEMO] Starting controller...", flush=True)
        time.sleep(3)
        if controller.poll() is not None:
            raise RuntimeError("Controller exited. Check demo-logs/controller.log")
        net = Mininet(topo=SDNServiceTopo(), controller=None, switch=OVSSwitch,
                      autoSetMacs=True, build=False)
        net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)
        net.build()
        print("[DEMO] Starting Mininet...", flush=True)
        net.start()
        time.sleep(3)

        def start_agent(host, binary, logfile):
            stream = open(log_dir / logfile, "w")
            service_logs.append(stream)
            host_processes.append(host.popen([str(ROOT / binary)],
                                             stdout=stream, stderr=subprocess.STDOUT))

        h1, h2, h3 = (net.get(n) for n in ("h1", "h2", "h3"))
        print("[DEMO] Starting registry and service agents...", flush=True)
        start_agent(h1, "registry", "registry.log")
        time.sleep(1)
        start_agent(h2, "server", "http-agent.log")
        start_agent(h3, "ftp_server", "ftp-agent.log")
        time.sleep(2)

        print("\nEverything is running. At the Mininet prompt, try:")
        print("  h4 ./client HTTP")
        print("  h4 ./client FTP")
        print("  pingall")
        print("  link s2 s3 down     (test backup route)")
        print("  link s2 s3 up")
        print("  exit                (shut down all components)")
        print("\nLogs: demo-logs/\n", flush=True)
        CLI(net)
    finally:
        for p in host_processes:
            if p.poll() is None: p.terminate()
        for p in host_processes:
            try: p.wait(timeout=2)
            except subprocess.TimeoutExpired: p.kill()
        if net is not None: net.stop()
        if controller.poll() is None:
            controller.terminate()
            try: controller.wait(timeout=3)
            except subprocess.TimeoutExpired: controller.kill()
        for stream in service_logs: stream.close()
        controller_log.close()
        print("[DEMO] Shut down complete. If needed: sudo mn -c", flush=True)

if __name__ == "__main__":
    main()
