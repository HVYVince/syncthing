import base64
import socket
import ssl
import BEP
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


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
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, capath="cert.pem")
ssl_sock = ssl.SSLContext.wrap_socket(context, sock)
ssl_sock.connect(("129.194.186.177", 22000))

hello = BEP.Hello()
hello.device_name = "MichelLazeyras.local"
hello.client_name = "SimpleSyncthing"
hello.client_version = "v0.0.1"
hellom = hello.SerializeToString()
print hellom
packet = bytearray.fromhex("2EA7D90B")
print packet
packet += bytearray(len(hellom))
packet += hellom
ssl_sock.send(hello.SerializeToString())
print ssl_sock.recv()
ssl_sock.close()



