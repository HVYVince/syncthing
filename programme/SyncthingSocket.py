import socket
import ssl
import BEPv1_pb2 as bep
import struct
import lz4.block as lz4

"""
Authors : Da Silva Marques Gabriel, Tournier Vincent
Date    : January 2018
Version : 0.1

Description : Everything about socket is here
"""


class SyncthingSocket(object):
    """
    Class used to create, send and receive packet through socket
    """
    def __init__(self, ip, port, cert, keyfile):
        """ Initialize the connection with the syncthing server

        :param ip: ip of destination
        :param port: port of destination
        :param cert: certificate to identify yourself
        :param keyfile: key to prove who you are
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, capath=cert)
        context.check_hostname = False
        context.load_cert_chain(cert, keyfile)
        self.ssl_sock = ssl.SSLContext.wrap_socket(context, sock)
        self.ssl_sock.connect((ip, port))
        return

    def receive(self, byteLength):
        """ Read byteLength bytes from socket

        :param byteLength: length we want to read from socket
        :return: what we read
        """
        chunks = []
        bytes_recd = 0
        while bytes_recd < byteLength:
            chunk = self.ssl_sock.recv(min(byteLength - bytes_recd, 2048))
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            chunks.append(chunk)
            bytes_recd += len(chunk)
        return b''.join(chunks)

    def is_message_available(self, hello_expected=False, cluster_expected=False):
        """ Check if a message is available

        If a hello or a cluster_config is expected we process them directly here and raise an error if we receive
        something else

        :param hello_expected: True if the next message MUST be a hello
        :param cluster_expected: True if the next message MUST be a cluster config
        :return: a message in is bep format, a string containing format
        """
        try:
            if hello_expected:
                if not bytes(self.receive(4)).__eq__(0x2EA7D90B):
                    self.ssl_sock.close()
                    raise Exception("HELLO NOT RECEIVED")
                hello_len = struct.unpack("!H", self.receive(2))[0]
                return bep.Hello.FromString(self.receive(hello_len))

            header_len = struct.unpack("!H", self.receive(2))[0]
            header_data = bytes(self.receive(header_len))
            message_len = struct.unpack("!I", self.receive(4))[0]
            byte_count = 0
            data = bytes()  # will contain the message

            # receive all bytes from message
            while message_len > byte_count:
                data += bytes(self.receive(message_len - byte_count))
                byte_count = len(data)

        except ssl.SSLError:
            return None
        except socket.timeout:
            return None

        header = bep.Header.FromString(header_data)
        # if a cluster_config is expected and we don't receive it we quit the program
        if cluster_expected and header.type != bep.MessageType.Value("CLUSTER_CONFIG"):
            self.ssl_sock.close()
            raise Exception("CLUSTER CONFIG NOT RECEIVED")

        if header.compression == bep.MessageCompression.Value("LZ4"):
            uncompressed_len = struct.unpack("!I", data[0:4])[0]
            data = lz4.decompress(data[4:], uncompressed_size=uncompressed_len)

        if header.type == bep.MessageType.Value("CLUSTER_CONFIG"):
            return bep.ClusterConfig.FromString(data), "CLUSTER_CONFIG"
        elif header.type == bep.MessageType.Value("INDEX"):
            return bep.Index.FromString(data), "INDEX"
        elif header.type == bep.MessageType.Value("INDEX_UPDATE"):
            return bep.IndexUpdate.FromString(data), "INDEX_UPDATE"
        elif header.type == bep.MessageType.Value("REQUEST"):
            return bep.Request.FromString(data), "REQUEST"
        elif header.type == bep.MessageType.Value("RESPONSE"):
            return bep.Response.FromString(data), "RESPONSE"
        elif header.type == bep.MessageType.Value("PING"):
            return bep.Ping.FromString(data), "PING"
        elif header.type == bep.MessageType.Value("CLOSE"):
            return bep.Close.FromString(data), "CLOSE"
        else:
            return None

    def send(self, message, message_type, hello=False):
        """ Send a packet trought socket

        :param message: the bep message to send
        :param message_type: type of bep message
        :param hello: True if it's a hello to send
        :return:
        """
        if hello:
            hello_message = message.SerializeToString()
            packet = struct.pack("!I", 0x2EA7D90B)
            packet += struct.pack("!H", len(hello_message))
            packet += hello_message
            self.ssl_sock.send(packet)
            return

        header = bep.Header()
        header.compression = bep.MessageCompression.Value("NONE")
        header.type = message_type
        header_message = header.SerializeToString()
        serial = message.SerializeToString()
        header_len = len(header_message)
        serial_len = len(serial)

        packet = struct.pack("!H", header_len)
        packet += header_message
        packet += struct.pack("!I", serial_len)
        packet += serial
        self.ssl_sock.send(packet)
        return

    def close(self):
        """ Close connection

        :return:
        """
        self.ssl_sock.close()
        return