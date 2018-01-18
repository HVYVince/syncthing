import os
import BEPv1_pb2 as bep

"""
Authors : Tournier Vincent, Da Silva Marques Gabriel
Date    : January 2018
Version : 0.1

Description : Manage files requests and responses
"""

class IndexManager(object):
    """
    Manage files requests and responses

    """

    def __init__(self, syncsock, ping, f_target):
        """ Initialize the IndexManager to send one request and wait for response before next request

        :param syncsock: socket trought which send requests
        :param ping: ping to reset after each communication
        :param f_target: local destination of shared folder
        """
        global FOLDER_TARGET
        self.files = []  # list of files to syncronize
        self.called = []  # list of boolean matching with self.files telling if a file has been called or not
        self.received = []  # list of boolean matching with self.files telling if a file has been received or not
        self.directories = []  # list of directories
        self.sock = syncsock
        self.ping = ping
        FOLDER_TARGET = f_target
        return

    def add_index(self, message):
        """ To call for every index or indexUpdate received

        Will create each folder and set permissions and modification time for it.
        Every file will be saved to be called later one by one

        :param message: message of type index/indexUpdate
        :return:
        """
        for message_file in message.files:
            if message_file.deleted:
                continue
            found = False

            # creation of folders
            if message_file.type == bep.FileInfoType.Value("DIRECTORY"):
                os.makedirs(FOLDER_TARGET + message.folder + "/" + message_file.name, exist_ok=True)
                # set permissions if they are
                if message_file.no_permissions:
                    os.chmod(FOLDER_TARGET + message.folder + "/" + message_file.name, 0o666)
                else:
                    os.chmod(FOLDER_TARGET + message.folder + "/" + message_file.name, message_file.permissions)
                # set modification time of folder
                os.utime(FOLDER_TARGET + message.folder + "/" + message_file.name, times=(message_file.modified_s, message_file.modified_s))
                self.directories.append((message.folder, message_file))
                continue

            for file in self.files:
                if file[1].name == message_file.name:
                    found = True
                    break
            if not found:
                self.files.append((message.folder, message_file))  # add a new file to request
                self.called.append(False)  # this file hasn't been called yet
                self.received.append(False)  # this file hasn't been received yet

        print("total files and symlinks : " + str(len(self.files)))
        print("total files to request : " + str(len(self.called)))
        print("total files to receive : " + str(len(self.received)))
        return

    def print_files(self):
        """ Print all files registered

        :return:
        """
        for file in self.files:
            print("INDEX FOR : " + file[0] + "/" + file[1].name)
        return

    def send_next_packet(self, i=-1):
        """ Send a request for a file or creat a symlink

        :param i: if set, the packet to send
        :return:
        """
        if i == -1:
            i = 0
            # looking for a packet not called
            while self.called[i]:
                i += 1
        folder = self.files[i][0]
        file = self.files[i][1]

        # we directly create symlinks
        if file.type == bep.FileInfoType.Value("SYMLINK"):
            try:
                print("Symlink target : " + file.symlink_target)
                os.symlink(FOLDER_TARGET + folder + "/" + file.symlink_target, FOLDER_TARGET + folder + "/" + file.name)
                self.received[i] = True
            except FileExistsError:
                print("symlink to " + FOLDER_TARGET + folder + "/" + file.symlink_target + " already exists")
                self.received[i] = True
       
        # else send request for file
        else:
            request = bep.Request()
            request.id = i
            request.folder = folder
            request.name = file.name
            request.offset = 0
            request.size = file.size
            request.from_temporary = False
            self.sock.send(request, bep.MessageType.Value("REQUEST"))
            self.ping.reset_timer()
        self.called[i] = True
        return

    def req_all_missing(self):
        """ Send request for files that hasn't been recceived yet

        :return: False if all files have been received
        """
        found = False
        for i in range(0, len(self.received)):
            if not self.received[i]:
                self.send_next_packet(i)
                print("missing " + str(i))
                found = True
        return found

    def acknowledge(self, req_id):
        """ Acknowledge a file and send another request if exists

        :param req_id: id of request to acknowledge 
        :return:
        """
        self.received[req_id] = True
        self.send_next_packet()
        return

    def get_request(self, req_id):
        """ return the request of index req_id

        :param req_id: id of the request to get
        :return: request of matching req_id
        """
        return self.files[req_id]
