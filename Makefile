.PHONY: all clean help controller topology registry-run http ftp discover cleanup

CC := gcc
CFLAGS := -Wall -Wextra -std=c11 -D_DEFAULT_SOURCE
ROOT := $(CURDIR)
SDN_DIR := $(ROOT)/member2
OSKEN_ENV ?= $(HOME)/osken-env
CTRL_IP ?= $(shell hostname -I | awk '{print $$1}')
SERVICE ?= HTTP

PROGRAMS := registry server ftp_server client

all: $(PROGRAMS)

registry: registry.c common.h
	$(CC) $(CFLAGS) registry.c -o registry

server: server.c common.h
	$(CC) $(CFLAGS) server.c -o server

ftp_server: ftp_server.c common.h
	$(CC) $(CFLAGS) ftp_server.c -o ftp_server

client: client.c common.h
	$(CC) $(CFLAGS) client.c -o client

clean:
	rm -f $(PROGRAMS)

help:
	@echo "Build all C programs: make"
	@echo "Clean binaries:       make clean"
	@echo "Start controller:     make controller"
	@echo "Start Mininet:        make topology"
	@echo "Start registry:       make registry-run"
	@echo "Start HTTP agent:     make http"
	@echo "Start FTP agent:      make ftp"
	@echo "Discover a service:   make discover SERVICE=HTTP (or FTP)"
	@echo "Clean Mininet:        make cleanup"
	@echo ""
	@echo "Keep the controller and Mininet running in separate terminals."
	@echo "Start the controller first, then start the topology."

# Run in Terminal 1 and leave it running.
controller:
	cd $(SDN_DIR) && . $(OSKEN_ENV)/bin/activate && python run_sdn_controller.py

# Run in Terminal 2 after the controller has started.
topology:
	@echo "Using controller IP: $(CTRL_IP)"
	cd $(SDN_DIR) && sudo mn --custom sdn_topology.py --topo sdnservice --controller=remote,ip=$(CTRL_IP),port=6653 --switch ovsk,protocols=OpenFlow13

# Launch each C program inside its corresponding Mininet host namespace.
registry-run: registry
	sudo mnexec -a "$$(pgrep -f 'mininet:h1' | head -n 1)" $(ROOT)/registry

http: server
	sudo mnexec -a "$$(pgrep -f 'mininet:h2' | head -n 1)" $(ROOT)/server

ftp: ftp_server
	sudo mnexec -a "$$(pgrep -f 'mininet:h3' | head -n 1)" $(ROOT)/ftp_server

discover: client
	sudo mnexec -a "$$(pgrep -f 'mininet:h4' | head -n 1)" $(ROOT)/client $(SERVICE)

cleanup:
	sudo mn -c
