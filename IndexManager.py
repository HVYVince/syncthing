import os
import BEPv1_pb2 as bep

class IndexManager(object):

    def __init__(self, syncsock, ping, f_target):
        global FOLDER_TARGET
        self.files = []
        self.called = []
        self.received = []
        self.directories = []
        self.sock = syncsock
        self.ping = ping
        FOLDER_TARGET = f_target
        return

    def add_index(self, message):
        for message_file in message.files:
            if message_file.deleted:
                continue
            found = False

            if message_file.type == bep.FileInfoType.Value("DIRECTORY"):
                os.makedirs(FOLDER_TARGET + message.folder + "/" + message_file.name, exist_ok=True)
                if message_file.no_permissions:
                    os.chmod(FOLDER_TARGET + message.folder + "/" + message_file.name, 0o666)
                else:
                    os.chmod(FOLDER_TARGET + message.folder + "/" + message_file.name, message_file.permissions)
                os.utime(FOLDER_TARGET + message.folder + "/" + message_file.name, times=(message_file.modified_s, message_file.modified_s))
                self.directories.append((message.folder, message_file))
                continue
            for file in self.files:
                if file[1].name == message_file.name:
                    found = True
                    break
            if not found:
                self.files.append((message.folder, message_file))
                self.called.append(False)
                self.received.append(False)

        print(len(self.files))
        print(len(self.called))
        print(len(self.received))
        return

    def print_files(self):
        for file in self.files:
            print("INDEX FOR : " + file[0] + "/" + file[1].name)
        return

    def send_next_packet(self, i=-1):
        if i == -1:
            i = 0
            while self.called[i]:
                i += 1
        folder = self.files[i][0]
        file = self.files[i][1]
        os.makedirs(FOLDER_TARGET + folder, exist_ok=True)

        # we directly create symlinks
        if file.type == bep.FileInfoType.Value("SYMLINK"):
            try:
                print("Symlink target : " + file.symlink_target)
                os.symlink(FOLDER_TARGET + folder + "/" + file.symlink_target, FOLDER_TARGET + folder + "/" + file.name)
                self.received[i] = True
            except FileExistsError:
                print("symlink to " + FOLDER_TARGET + folder + "/" + file.symlink_target + " already exists")
                self.received[i] = True
            # os.utime(folder, times=(file.modified_s, file.modified_s))
        # else send request for files
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
        found = False
        for i in range(0, len(self.received)):
            if not self.received[i]:
                self.send_next_packet(i)
                print("missing " + str(i))
                found = True
        return found

    def acknowledge(self, req_id):
        self.received[req_id] = True
        self.send_next_packet()
        return

    def get_request(self, req_id):
        return self.files[req_id]
