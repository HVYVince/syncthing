import base64
import SyncthingSocket
import struct
import socket
import ssl
import BEP
import lz4.block as lz4
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
MAX_SSL_FRAME = 16384


def generate_luhn_char(datas):
    factor = 2
    if len(datas) % 2 == 1:
        factor = 1
    total = 0
    n = len(BASE32_ALPHABET)
    for i in range(len(datas) - 1, -1, -1):
        codepoint = BASE32_ALPHABET.index(datas[i])
        addend = factor * codepoint
        if factor == 2:
            factor = 1
        else:
            factor = 2
        addend = (addend / n) + (addend % n)
        total += addend
    remainder = total % n
    check = (n - remainder) % n
    return BASE32_ALPHABET[check]


def format_id(hashstring):
    resultstring = ""
    if len(hashstring) != 56:
        return
    for i in range(0, 4):
        substring = hashstring[i * 13:(i + 1) * 13]
        chksm = generate_luhn_char(substring)
        for j in range(0, 2):
            resultstring += substring[j * 7 : (j + 1) * 7]
            if j == 0:
                resultstring += "-"
            else:
                resultstring += chksm + "-"
    return resultstring[:len(resultstring) - 1]


cert = x509.load_pem_x509_certificate(open("cert.pem", "r").read(), default_backend())
certHash = base64.b32encode(cert.fingerprint(hashes.SHA256()))
device_id = format_id(certHash)

sock = SyncthingSocket.SyncthingSocket("129.194.186.177", 22000, "cert.pem", "key.pem")

hello = BEP.Hello()
hello.device_name = "MichelLazeyras"
hello.client_name = "SimpleSyncthing"
hello.client_version = "v0.0.1"
sock.send(hello, -1, hello=True)

hello = sock.is_message_available(hello_expected=True)
if hello is None:
    exit()
print "SimpleSyncthing : We're conntected to " + hello.device_name + " " + hello.client_name

cluster = sock.is_message_available(cluster_expected=True)[0]
if cluster is None:
    exit()

loc_cluster = BEP.ClusterConfig()
for folder in cluster.folders:
    loc_f = loc_cluster.folders.add()
    dev = loc_f.devices.add()
    for device in folder.devices:
        if device.name == "MichelLazeyras":
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


sock.send(loc_cluster, BEP.MessageType.Value("CLUSTER_CONFIG"))

running = True
while running:
    message_tuple = sock.is_message_available()
    if message_tuple is None:
        print "nothing, closing"
        running = False
        break

    message = message_tuple[0]
    m_type = message_tuple[1]
    print m_type

sock.close()




