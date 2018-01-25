import time
import BEPv1_pb2 as bep
from threading import Thread

"""
Authors : Da Silva Marques Gabriel, Tournier Vincent
Date    : January 2018
Version : 0.1

Description : Thread which send a bep ping periodically.
"""


class Pinger(Thread):

    def __init__(self,sock, t):
        """ Initialise the thread with the wait time in seconds and send a bep packet by socket

        :param sock: socket where to send the packet
        :param t: time in seconds to wait before packet sending
        """
        Thread.__init__(self)
        self.time = t
        self.sock = sock
        self.strt = time.time()

    def run(self):
        """ Start the pinger. A ping will be sent each t seconds

        :return:
        """
        while True:
            # if t time has passed since self.strt we send a ping
            if (time.time() - self.strt) >= self.time:
                ping = bep.Ping()
                self.sock.send(ping, bep.MessageType.Value("PING"))
                self.strt = time.time()  # reset timer
                print("ping sent")

    def reset_timer(self):
        """ Reset the timer

        :return:
        """
        self.strt = time.time()

