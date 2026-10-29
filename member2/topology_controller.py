from os_ken.base import app_manager

from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    DEAD_DISPATCHER,
    set_ev_cls
)

from os_ken.ofproto import ofproto_v1_3

from os_ken.lib import hub

from os_ken.lib.packet import (
    packet,
    ethernet,
    ether_types
)

from os_ken.topology import event
from os_ken.topology import switches

from os_ken.topology.api import get_switch, get_link

import networkx as nx


class TopologyAwareController(app_manager.OSKenApp):

    # =========================================================
    # OPENFLOW VERSION
    # =========================================================

    OFP_VERSIONS = [
        ofproto_v1_3.OFP_VERSION
    ]

    # =========================================================
    # LOAD OS-KEN TOPOLOGY DISCOVERY
    # =========================================================

    _CONTEXTS = {
        'switches': switches.Switches
    }

    # =========================================================
    # INITIALIZATION
    # =========================================================

    def __init__(self, *args, **kwargs):

        super(
            TopologyAwareController,
            self
        ).__init__(*args, **kwargs)

        # -----------------------------------------------------
        # CONNECTED SWITCHES
        # -----------------------------------------------------
        #
        # {
        #     dpid: datapath
        # }
        #

        self.datapaths = {}

        # -----------------------------------------------------
        # DIRECTED NETWORK GRAPH
        # -----------------------------------------------------
        #
        # Nodes:
        #     switch DPIDs
        #
        # Directed edges:
        #     switch -> switch
        #
        # Each edge stores the output port.
        #

        self.graph = nx.DiGraph()

        # -----------------------------------------------------
        # HOST TABLE
        # -----------------------------------------------------
        #
        # {
        #     MAC:
        #     {
        #         "dpid": switch_id,
        #         "port": switch_port
        #     }
        # }
        #

        self.hosts = {}

        # -----------------------------------------------------
        # SWITCH-TO-SWITCH PORT TABLE
        # -----------------------------------------------------
        #
        # {
        #     (source_dpid, destination_dpid):
        #         output_port
        # }
        #

        self.link_ports = {}

        # -----------------------------------------------------
        # SPANNING TREE
        # -----------------------------------------------------
        #
        # Undirected tree used ONLY for safe flooding.
        #

        self.spanning_tree = nx.Graph()

        # -----------------------------------------------------
        # TOPOLOGY UPDATE LOCK
        # -----------------------------------------------------

        self.topology_lock = hub.Semaphore()

        # -----------------------------------------------------
        # TOPOLOGY MONITOR THREAD
        # -----------------------------------------------------

        self.topology_thread = hub.spawn(
            self.topology_monitor
        )

        print(
            "[CONTROLLER] Topology-aware controller created."
        )

    # =========================================================
    # SWITCH CONNECTION
    # =========================================================

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath

        dpid = datapath.id

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # -----------------------------------------------------
        # SAVE DATAPATH
        # -----------------------------------------------------

        self.datapaths[dpid] = datapath

        # -----------------------------------------------------
        # ADD SWITCH TO GRAPH
        # -----------------------------------------------------

        with self.topology_lock:

            self.graph.add_node(dpid)

        # -----------------------------------------------------
        # TABLE-MISS FLOW
        # -----------------------------------------------------
        #
        # Packets without a matching flow are sent
        # to the controller.
        #

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow_mod)

        print(
            "[SDN] Switch connected:",
            dpid
        )

        print(
            "[SDN] Table-miss flow installed on switch",
            dpid
        )

    # =========================================================
    # SWITCH STATE CHANGE
    # =========================================================

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, ev):

        datapath = ev.datapath

        if datapath is None:
            return

        dpid = datapath.id

        # -----------------------------------------------------
        # SWITCH CONNECTED
        # -----------------------------------------------------

        if ev.state == MAIN_DISPATCHER:

            if dpid not in self.datapaths:

                self.datapaths[dpid] = datapath

                print(
                    "[SDN] Switch entered MAIN state:",
                    dpid
                )

        # -----------------------------------------------------
        # SWITCH DISCONNECTED
        # -----------------------------------------------------

        elif ev.state == DEAD_DISPATCHER:

            if dpid in self.datapaths:

                del self.datapaths[dpid]

                print(
                    "[SDN] Switch disconnected:",
                    dpid
                )

    # =========================================================
    # TOPOLOGY MONITOR
    # =========================================================
    #
    # Periodically asks OS-Ken's topology module for the
    # currently discovered switches and links.
    #
    # This gives us a simple and reliable topology database.
    #

    def topology_monitor(self):

        while True:

            try:

                self.update_topology()

            except Exception as e:

                print(
                    "[TOPOLOGY] Update error:",
                    e
                )

            hub.sleep(2)

    # =========================================================
    # UPDATE TOPOLOGY
    # =========================================================

    def update_topology(self):

        switches_list = get_switch(
            self,
            None
        )

        links_list = get_link(
            self,
            None
        )

        new_graph = nx.DiGraph()

        new_link_ports = {}

        # -----------------------------------------------------
        # ADD SWITCHES
        # -----------------------------------------------------

        for switch in switches_list:

            dpid = switch.dp.id

            new_graph.add_node(dpid)

        # -----------------------------------------------------
        # ADD DIRECTED LINKS
        # -----------------------------------------------------

        for link in links_list:

            src_dpid = link.src.dpid
            dst_dpid = link.dst.dpid

            src_port = link.src.port_no

            # Add directed edge

            new_graph.add_edge(
                src_dpid,
                dst_dpid,
                port=src_port
            )

            # Save output port

            new_link_ports[
                (src_dpid, dst_dpid)
            ] = src_port

        # -----------------------------------------------------
        # BUILD SPANNING TREE
        # -----------------------------------------------------
        #
        # Convert directed graph to undirected graph.
        #
        # The spanning tree contains no cycles.
        #

        undirected_graph = nx.Graph()

        undirected_graph.add_nodes_from(
            new_graph.nodes()
        )

        for src, dst in new_graph.edges():

            undirected_graph.add_edge(
                src,
                dst
            )

        if len(undirected_graph.nodes()) > 0:

            new_spanning_tree = nx.minimum_spanning_tree(
                undirected_graph
            )

        else:

            new_spanning_tree = nx.Graph()

        # -----------------------------------------------------
        # UPDATE CONTROLLER DATABASE
        # -----------------------------------------------------

        with self.topology_lock:

            self.graph = new_graph

            self.link_ports = new_link_ports

            self.spanning_tree = new_spanning_tree

        # -----------------------------------------------------
        # DISPLAY TOPOLOGY
        # -----------------------------------------------------

        if new_graph.number_of_nodes() > 0:

            print(
                "[TOPOLOGY] Switches:",
                sorted(new_graph.nodes())
            )

        if new_graph.number_of_edges() > 0:

            print(
                "[TOPOLOGY] Links:",
                list(new_graph.edges())
            )

        if new_spanning_tree.number_of_edges() > 0:

            print(
                "[TOPOLOGY] Flooding tree:",
                list(new_spanning_tree.edges())
            )

    # =========================================================
    # TOPOLOGY EVENTS
    # =========================================================
    #
    # These events trigger an immediate topology refresh.
    #

    @set_ev_cls(
        event.EventSwitchEnter
    )
    def switch_enter_handler(self, ev):

        print(
            "[TOPOLOGY] Switch entered topology."
        )

        self.update_topology()

    @set_ev_cls(
        event.EventSwitchLeave
    )
    def switch_leave_handler(self, ev):

        print(
            "[TOPOLOGY] Switch left topology."
        )

        self.update_topology()

    @set_ev_cls(
        event.EventLinkAdd
    )
    def link_add_handler(self, ev):

        print(
            "[TOPOLOGY] Link added."
        )

        self.update_topology()

    @set_ev_cls(
        event.EventLinkDelete
    )
    def link_delete_handler(self, ev):

        print(
            "[TOPOLOGY] Link deleted."
        )

        self.update_topology()

    # =========================================================
    # ADD FLOW
    # =========================================================

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions
    ):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions
        )

        datapath.send_msg(flow_mod)

    # =========================================================
    # LEARN HOST
    # =========================================================

    def learn_host(
        self,
        mac,
        dpid,
        port
    ):

        # -----------------------------------------------------
        # DO NOT LEARN SWITCH LINK PORTS AS HOST PORTS
        # -----------------------------------------------------

        if (
            dpid,
            port
        ) in self.get_inter_switch_ports():

            return

        # -----------------------------------------------------
        # SAVE HOST LOCATION
        # -----------------------------------------------------

        old_location = self.hosts.get(mac)

        new_location = {
            "dpid": dpid,
            "port": port
        }

        self.hosts[mac] = new_location

        # -----------------------------------------------------
        # DISPLAY ONLY WHEN LOCATION CHANGES
        # -----------------------------------------------------

        if old_location != new_location:

            print(
                "[HOST] Learned:",
                mac,
                "-> switch",
                dpid,
                "port",
                port
            )

    # =========================================================
    # GET INTER-SWITCH PORTS
    # =========================================================

    def get_inter_switch_ports(self):

        ports = set()

        with self.topology_lock:

            for (
                src_dpid,
                dst_dpid
            ), port in self.link_ports.items():

                ports.add(
                    (src_dpid, port)
                )

        return ports

    # =========================================================
    # GET OUTPUT PORT
    # =========================================================

    def get_output_port(
        self,
        current_dpid,
        next_dpid
    ):

        with self.topology_lock:

            return self.link_ports.get(
                (
                    current_dpid,
                    next_dpid
                )
            )

    # =========================================================
    # CALCULATE SHORTEST PATH
    # =========================================================

    def get_shortest_path(
        self,
        source_dpid,
        destination_dpid
    ):

        with self.topology_lock:

            graph_copy = self.graph.copy()

        try:

            path = nx.shortest_path(
                graph_copy,
                source=source_dpid,
                target=destination_dpid
            )

            return path

        except nx.NetworkXNoPath:

            return None

        except nx.NodeNotFound:

            return None

    # =========================================================
    # INSTALL PATH
    # =========================================================

    def install_path(
        self,
        src_mac,
        dst_mac
    ):

        # -----------------------------------------------------
        # CHECK SOURCE HOST
        # -----------------------------------------------------

        if src_mac not in self.hosts:

            return False

        # -----------------------------------------------------
        # CHECK DESTINATION HOST
        # -----------------------------------------------------

        if dst_mac not in self.hosts:

            return False

        source_info = self.hosts[src_mac]

        destination_info = self.hosts[dst_mac]

        source_dpid = source_info["dpid"]

        destination_dpid = destination_info["dpid"]

        # -----------------------------------------------------
        # SAME SWITCH
        # -----------------------------------------------------

        if source_dpid == destination_dpid:

            datapath = self.datapaths.get(
                source_dpid
            )

            if datapath is None:

                return False

            parser = datapath.ofproto_parser

            match = parser.OFPMatch(
                eth_dst=dst_mac
            )

            actions = [
                parser.OFPActionOutput(
                    destination_info["port"]
                )
            ]

            self.add_flow(
                datapath,
                100,
                match,
                actions
            )

            print(
                "[PATH]",
                src_mac,
                "->",
                dst_mac,
                "same switch",
                source_dpid
            )

            return True

        # -----------------------------------------------------
        # FIND SHORTEST PATH
        # -----------------------------------------------------

        path = self.get_shortest_path(
            source_dpid,
            destination_dpid
        )

        if path is None:

            print(
                "[PATH] No path found:",
                source_dpid,
                "->",
                destination_dpid
            )

            return False

        print(
            "[PATH]",
            src_mac,
            "->",
            dst_mac,
            ":",
            path
        )

        # -----------------------------------------------------
        # INSTALL FLOW ON EVERY SWITCH
        # -----------------------------------------------------

        for index in range(
            len(path)
        ):

            current_dpid = path[index]

            datapath = self.datapaths.get(
                current_dpid
            )

            if datapath is None:

                return False

            parser = datapath.ofproto_parser

            # -------------------------------------------------
            # LAST SWITCH
            # -------------------------------------------------

            if index == len(path) - 1:

                output_port = destination_info[
                    "port"
                ]

            # -------------------------------------------------
            # INTERMEDIATE SWITCH
            # -------------------------------------------------

            else:

                next_dpid = path[
                    index + 1
                ]

                output_port = self.get_output_port(
                    current_dpid,
                    next_dpid
                )

                if output_port is None:

                    return False

            # -------------------------------------------------
            # FLOW MATCH
            # -------------------------------------------------

            match = parser.OFPMatch(
                eth_dst=dst_mac
            )

            actions = [
                parser.OFPActionOutput(
                    output_port
                )
            ]

            self.add_flow(
                datapath,
                100,
                match,
                actions
            )

            print(
                "[FLOW] Switch",
                current_dpid,
                "destination",
                dst_mac,
                "-> port",
                output_port
            )

        return True

    # =========================================================
    # LOOP-SAFE FLOODING
    # =========================================================

    def get_tree_ports(
        self,
        dpid
    ):

        ports = []

        with self.topology_lock:

            if dpid not in self.spanning_tree:

                return ports

            neighbors = list(
                self.spanning_tree.neighbors(
                    dpid
                )
            )

            for neighbor in neighbors:

                port = self.link_ports.get(
                    (
                        dpid,
                        neighbor
                    )
                )

                if port is not None:

                    ports.append(
                        port
                    )

        return ports

    # =========================================================
    # FLOOD PACKET SAFELY
    # =========================================================

    def flood_packet(
        self,
        msg,
        in_port
    ):

        datapath = msg.datapath

        ofproto = datapath.ofproto

        parser = datapath.ofproto_parser

        dpid = datapath.id

        actions = []

        # -----------------------------------------------------
        # TREE PORTS
        # -----------------------------------------------------

        tree_ports = self.get_tree_ports(
            dpid
        )

        for port in tree_ports:

            if port != in_port:

                actions.append(
                    parser.OFPActionOutput(
                        port
                    )
                )

        # -----------------------------------------------------
        # LEARNED HOST PORTS
        # -----------------------------------------------------
        #
        # Broadcast traffic must also reach hosts attached
        # directly to this switch.
        #

        for mac, info in self.hosts.items():

            if info["dpid"] != dpid:

                continue

            host_port = info["port"]

            if host_port == in_port:

                continue

            if host_port in tree_ports:

                continue

            if host_port not in [
                action.port
                for action in actions
                if hasattr(action, "port")
            ]:

                actions.append(
                    parser.OFPActionOutput(
                        host_port
                    )
                )

        # -----------------------------------------------------
        # NOTHING TO FORWARD
        # -----------------------------------------------------

        if not actions:

            return

        # -----------------------------------------------------
        # PACKET DATA
        # -----------------------------------------------------

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:

            data = msg.data

        # -----------------------------------------------------
        # PACKET OUT
        # -----------------------------------------------------

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

        print(
            "[FLOOD] Safe tree flood from switch",
            dpid,
            "ports",
            [
                action.port
                for action in actions
                if hasattr(action, "port")
            ]
        )

    # =========================================================
    # PACKET-IN HANDLER
    # =========================================================

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg

        datapath = msg.datapath

        ofproto = datapath.ofproto

        parser = datapath.ofproto_parser

        dpid = datapath.id

        # -----------------------------------------------------
        # INPUT PORT
        # -----------------------------------------------------

        in_port = msg.match.get(
            "in_port"
        )

        if in_port is None:

            return

        # -----------------------------------------------------
        # DECODE PACKET
        # -----------------------------------------------------

        pkt = packet.Packet(
            msg.data
        )

        eth = pkt.get_protocol(
            ethernet.ethernet
        )

        if eth is None:

            return

        # -----------------------------------------------------
        # IGNORE LLDP
        # -----------------------------------------------------

        if eth.ethertype == (
            ether_types.ETH_TYPE_LLDP
        ):

            return

        # -----------------------------------------------------
        # SOURCE / DESTINATION
        # -----------------------------------------------------

        src = eth.src

        dst = eth.dst

        # -----------------------------------------------------
        # LEARN SOURCE HOST
        # -----------------------------------------------------

        self.learn_host(
            src,
            dpid,
            in_port
        )

        # -----------------------------------------------------
        # BROADCAST
        # -----------------------------------------------------

        if dst == "ff:ff:ff:ff:ff:ff":

            self.flood_packet(
                msg,
                in_port
            )

            return

        # -----------------------------------------------------
        # MULTICAST
        # -----------------------------------------------------

        first_octet = int(
            dst.split(":")[0],
            16
        )

        if first_octet & 1:

            self.flood_packet(
                msg,
                in_port
            )

            return

        # -----------------------------------------------------
        # UNKNOWN DESTINATION
        # -----------------------------------------------------

        if dst not in self.hosts:

            print(
                "[SDN] Unknown destination:",
                dst
            )

            self.flood_packet(
                msg,
                in_port
            )

            return

        # -----------------------------------------------------
        # KNOWN DESTINATION
        # -----------------------------------------------------

        installed = self.install_path(
            src,
            dst
        )

        if not installed:

            print(
                "[SDN] Could not install path:",
                src,
                "->",
                dst
            )

            return

        # -----------------------------------------------------
        # DETERMINE OUTPUT PORT FOR CURRENT SWITCH
        # -----------------------------------------------------

        destination_info = self.hosts[
            dst
        ]

        destination_dpid = destination_info[
            "dpid"
        ]

        # -----------------------------------------------------
        # SAME SWITCH
        # -----------------------------------------------------

        if dpid == destination_dpid:

            out_port = destination_info[
                "port"
            ]

        else:

            path = self.get_shortest_path(
                dpid,
                destination_dpid
            )

            if path is None:

                return

            if len(path) < 2:

                return

            next_dpid = path[1]

            out_port = self.get_output_port(
                dpid,
                next_dpid
            )

            if out_port is None:

                return

        # -----------------------------------------------------
        # SEND CURRENT PACKET
        # -----------------------------------------------------

        actions = [
            parser.OFPActionOutput(
                out_port
            )
        ]

        data = None

        if msg.buffer_id == ofproto.OFP_NO_BUFFER:

            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )

        datapath.send_msg(out)

        print(
            "[FORWARD]",
            src,
            "->",
            dst,
            "switch",
            dpid,
            "port",
            out_port
        )
