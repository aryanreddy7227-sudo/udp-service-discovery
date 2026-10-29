# UDP-Based Service Discovery System with SDN

## Overview
A C-based UDP service discovery registry combined with SDN experiments using Mininet, Open vSwitch, and OS-Ken.

## Features
- Service registration, discovery, heartbeat tracking, and deregistration
- UDP registry on port 5000
- HTTP and FTP service advertisements
- OpenFlow 1.3 controllers and Mininet topologies
- MAC learning, topology discovery, and backup-route handling

## Requirements
- GCC
- Python 3
- Mininet and Open vSwitch
- OS-Ken and NetworkX

## Build
Run these commands from the project directory:

```bash
gcc registry.c -o registry
gcc client.c -o client
gcc server.c -o server
gcc ftp_server.c -o ftp_server
```

## UDP Protocol

The registry uses UDP port 5000 for service registration, discovery, heartbeats, and deregistration.

## Important Notes

- Service addresses must match the runtime network.
- The registry stores its service table in memory.
- The HTTP and FTP programs advertise services; they are not full application servers.
- The static backup-route controller and topology-aware controller are separate implementations.
- Compiled executables, Python cache files, temporary Xterm logs, and virtual environments are excluded by .gitignore.
