// Reference implementation for Load Balancing (Round Robin)
using System;
using System.Collections.Generic;

class LoadBalancer {
    private List<string> servers = new List<string> { "Server1", "Server2", "Server3" };
    private int lastServer = -1;

    public string GetNextServer() {
        lastServer = (lastServer + 1) % servers.Count;
        return servers[lastServer];
    }
}
