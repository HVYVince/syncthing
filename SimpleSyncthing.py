import SyncthingSocket
import IndexManager
import os
import BEPv1_pb2 as bep
from Pinger import Pinger
import argparse

"""
Authors : Da Silva Marques Gabriel, Tournier Vincent
Date    : January 2018
Version : 0.1

Description : Main program of syncthing client, only work for one first connection.
"""

DEVICE_NAME = "Gabi"

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--folder", required=True, help="destination path of shared folder")
args = vars(ap.parse_args())

# state 1 --> connexion TCP
# creation of connexion to syncthing repo with our certificate and key
sock = SyncthingSocket.SyncthingSocket("129.194.186.177", 22000, "cert.pem", "key.pem")

# start ping thread
ping = Pinger(sock, 90)
ping.start()

# state 2 --> sending hello
hello = bep.Hello()
hello.device_name = DEVICE_NAME
hello.client_name = "SimpleSyncthing"
hello.client_version = "v0.14.43"  # version of syncthing
sock.send(hello, -1, hello=True)
ping.reset_timer()  # reset of timer after each packet

# we wait for answer from server. Answer must be a Hello else we quit the program
hello = sock.is_message_available(hello_expected=True)
if hello is None:
    exit()

# Hello received
print("SimpleSyncthing : We're connected to " + hello.device_name + " " + hello.client_name)

# state 3 --> waiting for cluster config
cluster = sock.is_message_available(cluster_expected=True)[0]
print(cluster)
# if we don't receive a cluster config we quit the program
if cluster is None:
    exit()

# we copy folders of cluster config received to send them as ours
loc_cluster = bep.ClusterConfig()
for folder in cluster.folders:
    loc_f = loc_cluster.folders.add()
    loc_f.id = folder.id
    loc_f.read_only = folder.read_only
    loc_f.ignore_permissions = folder.ignore_permissions
    loc_f.ignore_delete = folder.ignore_delete
    loc_f.disable_temp_indexes = folder.disable_temp_indexes

# send our cluster config
sock.send(loc_cluster, bep.MessageType.Value("CLUSTER_CONFIG"))
ping.reset_timer()

# state 4 --> start transmissoin of files
# Indexmanager is used to manage the request command for each file
manager = IndexManager.IndexManager(sock, ping, args["folder"])

while True:
    message_tuple = sock.is_message_available()
    if message_tuple is None:
        print("Checking missing blocks")
        manager.req_all_missing()
        print("nothing to update")
        continue

    ping.reset_timer()
    message = message_tuple[0]
    m_type = message_tuple[1]

    if m_type == "INDEX" or m_type == "INDEX_UPDATE":
        manager.add_index(message)
        manager.send_next_packet()

    if m_type == "RESPONSE":
        manager.acknowledge(message.id)
        request = manager.get_request(message.id)[1] # get the request associated with the response
        filepath = IndexManager.FOLDER_TARGET + manager.get_request(message.id)[0] + "/"
        filepath += request.name
        try:
            folder_stat = os.stat(filepath)
            folder_time = (folder_stat.st_mtime, folder_stat.st_mtime)
        except FileNotFoundError:
            folder_time = (0, 0)

        # create file
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            print("writing " + filepath)
            f.write(message.data)
            if request.no_permissions:
                os.chmod(filepath, 0o666)
            else:
                os.chmod(filepath, request.permissions)

            os.utime(filepath, times=(request.modified_s, request.modified_s))
        if folder_time != (0, 0):
            os.utime(filepath, folder_time)
