import base64
import SyncthingSocket
import IndexManager
import os
import BEPv1_pb2 as bep
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from Pinger import Pinger
import argparse

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
MAX_SSL_FRAME = 16384

DEVICE_NAME = "Gabi"

# construct the argument parse and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-f", "--folder", required=True,
	help="destination path of shared folder")
args = vars(ap.parse_args())

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

manager = IndexManager.IndexManager(sock, ping, args["folder"])

while True:
    message_tuple = sock.is_message_available()
    if message_tuple is None:
        print("Checking missing blocks")
        manager.req_all_missing()
        print("nothing to update")
        continue

    message = message_tuple[0]
    m_type = message_tuple[1]

    if m_type == "INDEX" or m_type == "INDEX_UPDATE":
        manager.add_index(message)
        manager.send_next_packet()

    if m_type == "RESPONSE":
        manager.acknowledge(message.id)
        request = manager.get_request(message.id)[1]
        filepath = IndexManager.FOLDER_TARGET + manager.get_request(message.id)[0] + "/"
        filepath += request.name
        try:
            folder_stat = os.stat(filepath)
            folder_time = (folder_stat.st_mtime, folder_stat.st_mtime)
        except FileNotFoundError:
            folder_time = (0, 0)
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

sock.close()
