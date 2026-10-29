# UDP-Based Service Discovery System with SDN

## 1. Overview

A C-based UDP service discovery registry combined with Software-Defined Networking (SDN) experiments using Mininet, Open vSwitch (OVS), OpenFlow 1.3, and OS-Ken.

The registry allows service providers to register services and clients to discover available services using UDP messages.

## 2. Features

- Service registration and discovery
- Heartbeat-based service tracking
- Service deregistration
- UDP registry listening on port 5000
- HTTP and FTP service advertisements
- OpenFlow 1.3 controllers
- Mininet network topologies
- MAC learning and SDN routing experiments
- Backup-route handling in the static SDN controller
- Separate topology-aware controller implementation

## 3. Requirements

- GCC
- Python 3
- Mininet
- Open vSwitch
- OS-Ken
- NetworkX for the topology-aware controller

## 4. Build the C Programs

Run these commands from the project directory:

```bash
gcc registry.c -o registry
gcc client.c -o client
gcc server.c -o server
gcc ftp_server.c -o ftp_server
## 5. UDP Protocol

The registry uses UDP port 5000.

Example messages for the tested Mininet topology:

| Purpose | Example message |
|---|---|
| Register HTTP | `REGISTER|HTTP|10.0.0.3|8080` |
| Register FTP | `REGISTER|FTP|10.0.0.4|2121` |
| Discover HTTP | `DISCOVER|HTTP` |
| Discover FTP | `DISCOVER|FTP` |
| HTTP heartbeat | `HEARTBEAT|HTTP|10.0.0.3` |
| FTP heartbeat | `HEARTBEAT|FTP|10.0.0.4` |
| Deregister HTTP | `DEREGISTER|HTTP` |

Service IP addresses must match the runtime network configuration.

## 6. Mininet and SDN

The repository contains multiple topology and controller implementations:

- `member2/sdn_topology.py` — SDN service topology
- `member2/sdn_controller.py` — static SDN controller with backup-route handling
- `member2/topology_controller.py` — separate topology-aware controller
- `topology.py` — another service discovery topology
- `controller.py` — controller implementation

For the `member2` SDN topology, start the matching controller before connecting the Mininet switches.

Example Mininet launch command from the repository root:

```bash
sudo mn --custom member2/sdn_topology.py --topo sdnservice \
  --controller=remote,ip=127.0.0.1,port=6653 \
  --switch ovs,protocols=OpenFlow13
