from mininet.topo import Topo


class ServiceDiscoveryTopo(Topo):

    def build(self):

        # Create switch
        s1 = self.addSwitch('s1')

        # Create hosts
        registry = self.addHost(
            'h1',
            ip='10.0.0.2/24'
        )

        http_server = self.addHost(
            'h2',
            ip='10.0.0.3/24'
        )

        ftp_server = self.addHost(
            'h3',
            ip='10.0.0.4/24'
        )

        client = self.addHost(
            'h4',
            ip='10.0.0.5/24'
        )

        # Connect hosts to switch
        self.addLink(registry, s1)
        self.addLink(http_server, s1)
        self.addLink(ftp_server, s1)
        self.addLink(client, s1)


topos = {
    'servicediscovery': ServiceDiscoveryTopo
}
