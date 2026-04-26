void demo() { auto cluster = this_cluster(); kernel<<<1, 32>>>(); cluster.sync(); }
