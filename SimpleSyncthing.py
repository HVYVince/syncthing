import base64
import SyncthingSocket
import os
import BEPv1_pb2 as bep
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from Pinger import Pinger

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
MAX_SSL_FRAME = 16384

DEVICE_NAME = "Gabi"
#FOLDER_TARGET = "/Users/vincetournier/Documents/syncthing"
FOLDER_TARGET = "/home/gabriel/Bureau/bullshit/"
REQUEST_ID = 0


def generate_luhn_char(datas):
    factor = 2
    if len(datas) % 2 == 1:
        factor = 1
    total = 0
    n = len(BASE32_ALPHABET)
    for i in range(len(datas) - 1, -1, -1):
        codepoint = BASE32_ALPHABET.index(datas.decode('ascii')[i])
        addend = factor * codepoint
        if factor == 2:
            factor = 1
        else:
            factor = 2
        addend = (addend / n) + (addend % n)
        total += addend
    remainder = total % n
    check = (n - remainder) % n
    return BASE32_ALPHABET[int(check)]


def format_id(hashstring):
    resultstring = ""
    if len(hashstring) != 56:
        return
    for i in range(0, 4):
        substring = hashstring[i * 13:(i + 1) * 13]
        chksm = generate_luhn_char(substring)
        for j in range(0, 2):
            resultstring += substring[j * 7: (j + 1) * 7].decode('ascii')
            if j == 0:
                resultstring += "-"
            else:
                resultstring += chksm + "-"
    return resultstring[:len(resultstring) - 1]


cert = x509.load_pem_x509_certificate(open("cert.pem", "r").read().encode('ascii'), default_backend())
certHash = base64.b32encode(cert.fingerprint(hashes.SHA256()))
device_id = format_id(certHash)

sock = SyncthingSocket.SyncthingSocket("129.194.186.177", 22000, "cert.pem", "key.pem")

# start ping thread
ping = Pinger(sock, 90)
ping.start()

hello = bep.Hello()
hello.device_name = DEVICE_NAME
hello.client_name = "SimpleSyncthing"
hello.client_version = "v0.14.43"
sock.send(hello, -1, hello=True)
ping.reset_timer()

hello = sock.is_message_available(hello_expected=True)
if hello is None:
    exit()
print("SimpleSyncthing : We're connected to " + hello.device_name + " " + hello.client_name)

cluster = sock.is_message_available(cluster_expected=True)[0]
print(cluster)
if cluster is None:
    exit()

loc_cluster = bep.ClusterConfig()
for folder in cluster.folders:
    loc_f = loc_cluster.folders.add()
    dev = loc_f.devices.add()
    for device in folder.devices:
        if device.name == DEVICE_NAME:
            dev.name = device.name
            dev.id = device.id
            for address in device.addresses:
                dev.addresses.append(address)
            dev.compression = device.compression
            dev.cert_name = device.cert_name
            dev.max_sequence = device.max_sequence
            dev.introducer = device.introducer
            dev.skip_introduction_removals = device.skip_introduction_removals
    loc_f.id = folder.id
    loc_f.read_only = folder.read_only
    loc_f.ignore_permissions = folder.ignore_permissions
    loc_f.ignore_delete = folder.ignore_delete
    loc_f.disable_temp_indexes = folder.disable_temp_indexes


sock.send(loc_cluster, bep.MessageType.Value("CLUSTER_CONFIG"))
ping.reset_timer()

#print("", file=open("output.txt", "w"))

requestList = []
fileList = []

while True:

    message_tuple = sock.is_message_available()
    if message_tuple is None:
        print("nothing, closing")
        continue

    message = message_tuple[0]
    m_type = message_tuple[1]

    if m_type == "INDEX" or m_type == "INDEX_UPDATE":
        # folders creation
        os.makedirs(FOLDER_TARGET + message.folder, exist_ok=True)
        # Let's fill folders
        for file in message.files:
            # we don't request for deleted files
            if not file.deleted:
                folder = FOLDER_TARGET + message.folder + "/" + file.name
                # we directly create directories and symlinks
                if file.type == bep.FileInfoType.Value("DIRECTORY"):
                    os.makedirs(folder, exist_ok=True)
                    if file.no_permissions:
                        os.chmod(folder, 0o666)
                    else:
                        os.chmod(folder, file.permissions)
                        print(file.modified_s)
                    os.utime(folder, times=(file.modified_s, file.modified_s))
                # we directly create symlinks
                elif file.type == bep.FileInfoType.Value("SYMLINK"):
                    os.symlink(FOLDER_TARGET + message.folder + "/" + file.symlink_target, folder)
                    #os.utime(folder, times=(file.modified_s, file.modified_s))
                # else send request for files
                else:
                    request = bep.Request()
                    request.id = REQUEST_ID
                    request.folder = message.folder
                    request.name = file.name
                    request.offset = 0
                    request.size = file.size
                    request.from_temporary = False
                    # add request to request queue
                    requestList.append(request)
                    # add permissions
                    fileList.append(file)
                    sock.send(request, bep.MessageType.Value("REQUEST"))
                    ping.reset_timer()
                    REQUEST_ID += 1
        #print("---", file=open("output.txt", "a"))
        #print(message, file=open("output.txt", "a"))

    if m_type == "RESPONSE":
        response = requestList[message.id]
        folder = FOLDER_TARGET + response.folder + "/" + response.name
        try:
            folder_stat = os.stat(folder)
            folder_time = (folder_stat.st_mtime, folder_stat.st_mtime)
        except FileNotFoundError:
            folder_time = (0, 0)
        with open(folder, 'wb') as f:
            print("writing " + folder)
            f.write(message.data)
            if fileList[message.id].no_permissions:
                os.chmod(folder, 0o666)
            else:
                os.chmod(folder, fileList[message.id].permissions)
            os.utime(folder, times=(fileList[message.id].modified_s, fileList[message.id].modified_s))
        if folder_time != (0, 0):
            os.utime(folder, folder_time)

    # print(file, file=open("output.txt", "a"))

sock.close()
