import time
import BEPv1_pb2 as bep
from threading import Thread


class Pinger(Thread):

    def __init__(self,sock, t):
        Thread.__init__(self)
        self.time = t
        self.sock = sock
        self.strt = time.time()

    def run(self):
        while True:
            if (time.time() - self.strt) >= self.time:
                print("send PING")
                ping = bep.Ping()
                self.sock.send(ping, bep.MessageType.Value("PING"))
                self.strt = time.time()  # reset timer


    def reset_timer(self):
        self.strt = time.time()

