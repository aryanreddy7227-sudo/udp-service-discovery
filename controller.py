from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    MAIN_DISPATCHER,
    CONFIG_DISPATCHER,
    set_ev_cls
)

from os_ken.ofproto import ofproto_v1_3

from os_ken.lib.packet import (
    packet,
    ethernet,
    ether_types,
    udp
)


class UDPServiceController(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(UDPServiceController, self).__init__(*args, **kwargs)

        # MAC address table
        # Example:
        # {1: {'aa:bb:cc:dd:ee:ff': 1}}
        self.mac_to_port = {}

    # --------------------------------------------------
    # SWITCH CONNECTION
    # --------------------------------------------------

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss rule
        # Unknown packets are sent to the controller.
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
            datapath.id
        )

    # --------------------------------------------------
    # ADD FLOW
    # --------------------------------------------------

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

    # --------------------------------------------------
    # PACKET IN
    # --------------------------------------------------

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
	    # --------------------------------------------------
    # PORT FAILURE DETECTION
    # --------------------------------------------------

    @set_ev_cls(
        ofp_event.EventOFPPortStatus,
        MAIN_DISPATCHER
    )
    def port_status_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        desc = msg.desc

        if desc.state & datapath.ofproto.OFPPS_LINK_DOWN:

            print(
                "[SDN] LINK FAILURE detected:",
                "switch",
                datapath.id,
                "port",
                desc.port_no
            )
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        in_port = msg.match['in_port']

        # Parse packet
        pkt = packet.Packet(msg.data)

        # Ethernet header
        eth = pkt.get_protocol(
            ethernet.ethernet
        )

        if eth is None:
            return

        src = eth.src
        dst = eth.dst

        # Ignore LLDP packets
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        # --------------------------------------------------
        # LOG UDP PACKETS
        # --------------------------------------------------

        udp_pkt = pkt.get_protocol(udp)

        if udp_pkt is not None:

            print(
                "[SDN] UDP:",
                src,
                "->",
                dst,
                "destination port:",
                udp_pkt.dst_port
            )

        # --------------------------------------------------
        # MAC LEARNING
        # --------------------------------------------------

        dpid = datapath.id

        self.mac_to_port.setdefault(
            dpid,
            {}
        )

        # Learn source MAC
        self.mac_to_port[dpid][src] = in_port

        # --------------------------------------------------
        # FIND OUTPUT PORT
        # --------------------------------------------------

        if dst in self.mac_to_port[dpid]:

            out_port = self.mac_to_port[dpid][dst]

        else:

            out_port = ofproto.OFPP_FLOOD

        # --------------------------------------------------
        # CREATE OUTPUT ACTION
        # --------------------------------------------------

        actions = [
            parser.OFPActionOutput(
                out_port
            )
        ]

        # --------------------------------------------------
        # INSTALL FLOW
        # --------------------------------------------------

        if out_port != ofproto.OFPP_FLOOD:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                datapath,
                10,
                match,
                actions
            )

        # --------------------------------------------------
        # SEND PACKET OUT
        # --------------------------------------------------

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
            "[SDN] Packet:",
            src,
            "->",
            dst,
            "via port",
            out_port
        )
