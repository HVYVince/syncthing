import socket
import ssl
import BEPv1_pb2 as bep
import struct
import lz4.block as lz4

MAX_SSL_FRAME = 16384


class SyncthingSocket(object):

    def __init__(self, ip, port, cert, keyfile):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, capath=cert)
        context.check_hostname = False
        context.load_cert_chain(cert, keyfile)
        self.ssl_sock = ssl.SSLContext.wrap_socket(context, sock)
        self.ssl_sock.connect((ip, port))
        return

    def is_message_available(self, hello_expected=False, cluster_expected=False):
        try:
            receive = self.ssl_sock.recv(MAX_SSL_FRAME)

            if hello_expected:
                if not bytes(receive[0:4]).__eq__(0x2EA7D90B):
                    self.ssl_sock.close()
                    raise Exception("HELLO NOT RECEIVED")
                hello_len = struct.unpack("!H", receive[4:6])[0]
                return bep.Hello.FromString(receive[6:hello_len + 6])
            if cluster_expected:
                print("LOL")
                header_len = struct.unpack("!H", receive[0:2])[0]
                cluster_len = struct.unpack("!I", receive[2:6])[0]
                print(header_len)
                print(cluster_len)
                return bep.ClusterConfig.FromString(receive[6:cluster_len + 6])

            byte_count = len(receive)
            header_len = struct.unpack("!H", receive[0:2])[0]
            message_len = struct.unpack("!I", receive[header_len + 2:header_len + 6])[0]

            while message_len + header_len + 6 > MAX_SSL_FRAME and byte_count < message_len + header_len + 6:
                receive += self.ssl_sock.recv(min(MAX_SSL_FRAME, (message_len + header_len + 6) - byte_count))
                byte_count = len(receive)

        except ssl.SSLError:
            return None

        header = bep.Header.FromString(receive[2:header_len + 2])
        if cluster_expected and header.type != bep.MessageType.Value("CLUSTER_CONFIG"):
            self.ssl_sock.close()
            raise Exception("CLUSTER CONFIG NOT RECEIVED")

        data = receive[header_len + 6:message_len + header_len + 6]

        if header.compression == bep.MessageCompression.Value("LZ4"):
            print(bep.MessageCompression.Name(header.compression))
            uncompressed_len = struct.unpack("!I", data[0:4])[0]
            print(data[4:])
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
        self.ssl_sock.close()
        return
