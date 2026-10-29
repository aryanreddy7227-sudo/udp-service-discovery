from os_ken.base import app_manager

from os_ken.controller import ofp_event
from os_ken.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls

from os_ken.ofproto import ofproto_v1_3


class StaticSDNController(app_manager.OSKenApp):

    def __init__(self, *args, **kwargs):
        super(StaticSDNController, self).__init__(*args, **kwargs)
        self.datapaths = {}

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # Port map:
    #
    # s1:
    #   1 = h1
    #   2 = s2
    #   3 = s3
    #
    # s2:
    #   1 = h2
    #   2 = s1
    #   3 = s4
    #
    # s3:
    #   1 = h3
    #   2 = s1
    #   3 = s4
    #
    # s4:
    #   1 = h4
    #   2 = s2
    #   3 = s3

    ROUTES = {
        1: {
            "10.0.0.2": 1,
            "10.0.0.3": 2,
            "10.0.0.4": 2,
            "10.0.0.5": 2,
        },

        2: {
            "10.0.0.2": 2,
            "10.0.0.3": 1,
            "10.0.0.4": 3,
            "10.0.0.5": 3,
        },

        3: {
            "10.0.0.2": 2,
            "10.0.0.3": 2,
            "10.0.0.4": 1,
            "10.0.0.5": 3,
        },

        4: {
            "10.0.0.2": 2,
            "10.0.0.3": 2,
            "10.0.0.4": 2,
            "10.0.0.5": 1,
        },
    }

    def add_flow(self, datapath, priority, match, actions):

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

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

    def install_table_miss(self, datapath):

        parser = datapath.ofproto_parser

        match = parser.OFPMatch()

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=0,
            match=match,
            instructions=[]
        )

        datapath.send_msg(flow_mod)

    def install_ipv4_routes(self, datapath):

        parser = datapath.ofproto_parser
        dpid = datapath.id

        for destination_ip, output_port in self.ROUTES[dpid].items():

            match = parser.OFPMatch(
                eth_type=0x0800,
                ipv4_dst=destination_ip
            )

            actions = [
                parser.OFPActionOutput(output_port)
            ]

            self.add_flow(
                datapath,
                100,
                match,
                actions
            )

            print(
                "[SDN] IPv4 route:",
                "switch", dpid,
                "destination", destination_ip,
                "output", output_port
            )

    def install_arp_routes(self, datapath):

        parser = datapath.ofproto_parser
        dpid = datapath.id

        for destination_ip, output_port in self.ROUTES[dpid].items():

            match = parser.OFPMatch(
                eth_type=0x0806,
                arp_tpa=destination_ip
            )

            actions = [
                parser.OFPActionOutput(output_port)
            ]

            self.add_flow(
                datapath,
                90,
                match,
                actions
            )

            print(
                "[SDN] ARP route:",
                "switch", dpid,
                "target", destination_ip,
                "output", output_port
            )

    def install_backup_routes(self):

        parser = None

        BACKUP_ROUTES = {
            2: {
                "10.0.0.4": 4,
                "10.0.0.5": 4,
            },

            3: {
                "10.0.0.2": 3,
                "10.0.0.3": 3,
                "10.0.0.4": 1,
                "10.0.0.5": 3,
            },

            4: {
                "10.0.0.2": 3,
                "10.0.0.3": 3,
                "10.0.0.4": 2,
                "10.0.0.5": 1,
            },
        }

        for dpid, routes in BACKUP_ROUTES.items():

            if dpid not in self.datapaths:
                continue

            datapath = self.datapaths[dpid]
            parser = datapath.ofproto_parser

            for destination_ip, output_port in routes.items():

                match = parser.OFPMatch(
                    eth_type=0x0800,
                    ipv4_dst=destination_ip
                )

                actions = [
                    parser.OFPActionOutput(output_port)
                ]

                self.add_flow(
                    datapath,
                    200,
                    match,
                    actions
                )

                print(
                    "[SDN] BACKUP route:",
                    "switch", dpid,
                    "destination", destination_ip,
                    "output", output_port
                )

        for dpid, routes in BACKUP_ROUTES.items():

            if dpid not in self.datapaths:
                continue

            datapath = self.datapaths[dpid]
            parser = datapath.ofproto_parser

            for destination_ip, output_port in routes.items():

                match = parser.OFPMatch(
                    eth_type=0x0806,
                    arp_tpa=destination_ip
                )

                actions = [
                    parser.OFPActionOutput(output_port)
                ]

                self.add_flow(
                    datapath,
                    190,
                    match,
                    actions
                )

                print(
                    "[SDN] BACKUP ARP route:",
                    "switch", dpid,
                    "target", destination_ip,
                    "output", output_port
                )


    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id

        self.datapaths[dpid] = datapath

        print()
        print("==============================")
        print("[SDN] Switch connected:", dpid)
        print("==============================")

        self.install_table_miss(datapath)

        self.install_ipv4_routes(datapath)

        self.install_arp_routes(datapath)

        print(
            "[SDN] Configuration complete for switch",
            dpid
        )
    @set_ev_cls(
        ofp_event.EventOFPPortStatus,
        MAIN_DISPATCHER
    )
    def port_status_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        print()
        print("==============================")
        print("[SDN] PORT STATUS CHANGE")
        print("==============================")

        print(
            "[SDN] Switch:",
            datapath.id
        )

        print(
            "[SDN] Port:",
            msg.desc.port_no
        )

        print(
            "[SDN] Reason:",
            msg.reason
        )

        # If switch 2 loses port 3,
        # the s2-s3 primary link has failed.
        if datapath.id == 2 and msg.desc.port_no == 3:

            print("[SDN] Primary link s2-s3 FAILED")
            print("[SDN] Installing backup routes...")

            self.install_backup_routes()

            print("[SDN] Backup routing activated")
