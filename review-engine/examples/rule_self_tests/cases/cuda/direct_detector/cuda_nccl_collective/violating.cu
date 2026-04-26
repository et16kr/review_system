void demo() { ncclAllReduce(send, recv, count, ncclFloat, ncclSum, comm, stream); }
