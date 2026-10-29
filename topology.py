from mininet.topo import Topo


class ServiceDiscoveryTopo(Topo):

    def build(self):

        # Four switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        # Hosts
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

        # Hosts connected to edge switches
        self.addLink(registry, s1)
        self.addLink(http_server, s1)

        self.addLink(ftp_server, s3)
        self.addLink(client, s3)

        # First path: s1 -> s2 -> s3
        self.addLink(s1, s2)
        self.addLink(s2, s3)

        # Second/backup path: s1 -> s4 -> s3
        self.addLink(s1, s4)
        self.addLink(s4, s3)


topos = {
    'servicediscovery': ServiceDiscoveryTopo
}