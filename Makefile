.DEFAULT_GOAL := all

SHELL := /bin/bash
CC ?= gcc
PYTHON ?= python3
CFLAGS ?= -Wall -Wextra -std=c11 -D_DEFAULT_SOURCE
ROOT := $(abspath .)
SDN_DIR := $(ROOT)/member2
OSKEN_ENV ?= $(HOME)/osken-env
OSKEN_PYTHON ?= $(OSKEN_ENV)/bin/python
OSKEN ?= $(OSKEN_ENV)/bin/osken-manager
CTRL_IP ?= $(shell hostname -I | awk '{print $$1}')
OF_PORT ?= 6653
SERVICE ?= HTTP

C_PROGRAMS := registry server ftp_server client
PYTHON_FILES := topology.py topology_star_backup.py controller_backup.py \
	member2/sdn_topology.py member2/sdn_controller.py \
	member2/run_sdn_controller.py member2/topology_controller.py \
	member2/run_topology_controller.py

.PHONY: all build clean help check controller topology topology-main topology-star \
	controller-backup topology-controller registry-run http ftp discover cleanup

# Build all UDP service-discovery C executables.
all: build

build: $(C_PROGRAMS)

registry: registry.c common.h
	$(CC) $(CFLAGS) registry.c -o $@

server: server.c common.h
	$(CC) $(CFLAGS) server.c -o $@

ftp_server: ftp_server.c common.h
	$(CC) $(CFLAGS) ftp_server.c -o $@

client: client.c common.h
	$(CC) $(CFLAGS) client.c -o $@

# Syntax-check the maintained Python topology/controller entry points.
check: build
	$(PYTHON) -m py_compile $(PYTHON_FILES)

clean:
	rm -f $(C_PROGRAMS)
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

help:
	@echo "BUILD / CHECK"
	@echo "  make                         Build all four C programs"
	@echo "  make check                   Build C programs + check Python syntax"
	@echo "  make clean                   Remove generated binaries and Python caches"
	@echo ""
	@echo "MAIN SDN DEMO (use separate terminals)"
	@echo "  make controller              Start OS-Ken static-route controller"
	@echo "  make topology                Start member2 Mininet topology"
	@echo "  make registry-run            Run registry in h1"
	@echo "  make http                    Run HTTP agent in h2"
	@echo "  make ftp                     Run FTP agent in h3"
	@echo "  make discover SERVICE=HTTP   Discover HTTP from h4"
	@echo "  make discover SERVICE=FTP    Discover FTP from h4"
	@echo "  make cleanup                 Clean Mininet state"
	@echo ""
	@echo "ALTERNATIVE / EXPERIMENTAL FILES"
	@echo "  make topology-main           Start root topology.py"
	@echo "  make topology-star           Start root topology_star_backup.py"
	@echo "  make controller-backup       Start root controller_backup.py"
	@echo "  make topology-controller     Start topology-aware controller"
	@echo ""
	@echo "Start the controller first, then Mininet. Keep each foreground"
	@echo "process in its own terminal. Run these targets from the repo root."

# Main integrated SDN controller. Requires OS-Ken installed in OSKEN_ENV.
controller:
	cd $(SDN_DIR) && $(OSKEN_PYTHON) run_sdn_controller.py

# Main integrated Mininet topology; controller should already be running.
topology:
	@echo "Controller address: $(CTRL_IP):$(OF_PORT)"
	cd $(SDN_DIR) && sudo mn --custom sdn_topology.py --topo sdnservice --controller=remote,ip=$(CTRL_IP),port=$(OF_PORT) --switch ovsk,protocols=OpenFlow13

# Registry/service/client programs run inside the matching Mininet host namespace.
registry-run: registry
	@pid="$$(pgrep -f 'mininet:h1' | head -n 1)"; test -n "$$pid" || { echo "Mininet h1 not found. Start 'make topology' first."; exit 1; }
	sudo mnexec -a "$$pid" $(ROOT)/registry

http: server
	@pid="$$(pgrep -f 'mininet:h2' | head -n 1)"; test -n "$$pid" || { echo "Mininet h2 not found. Start 'make topology' first."; exit 1; }
	sudo mnexec -a "$$pid" $(ROOT)/server

ftp: ftp_server
	@pid="$$(pgrep -f 'mininet:h3' | head -n 1)"; test -n "$$pid" || { echo "Mininet h3 not found. Start 'make topology' first."; exit 1; }
	sudo mnexec -a "$$pid" $(ROOT)/ftp_server

discover: client
	@pid="$$(pgrep -f 'mininet:h4' | head -n 1)"; test -n "$$pid" || { echo "Mininet h4 not found. Start 'make topology' first."; exit 1; }
	sudo mnexec -a "$$pid" $(ROOT)/client $(SERVICE)

# Additional topologies/controllers retained in the repository.
topology-main:
	sudo mn --custom topology.py --topo servicediscovery --controller=remote,ip=$(CTRL_IP),port=$(OF_PORT) --switch ovsk,protocols=OpenFlow13

topology-star:
	sudo mn --custom topology_star_backup.py --topo servicediscovery --controller=remote,ip=$(CTRL_IP),port=$(OF_PORT) --switch ovsk,protocols=OpenFlow13

controller-backup:
	$(OSKEN) $(ROOT)/controller_backup.py

topology-controller:
	cd $(SDN_DIR) && $(OSKEN_PYTHON) run_topology_controller.py

cleanup:
	sudo mn -c
