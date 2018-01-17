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

    def receive(self, byteLength):
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
            data = bytes()

            while message_len > byte_count:
                data += bytes(self.receive(message_len - byte_count))
                byte_count = len(data)

        except ssl.SSLError:
            return None
        except socket.timeout:
            return None

        header = bep.Header.FromString(header_data)
        if cluster_expected and header.type != bep.MessageType.Value("CLUSTER_CONFIG"):
            self.ssl_sock.close()
            raise Exception("CLUSTER CONFIG NOT RECEIVED")

        if header.compression == bep.MessageCompression.Value("LZ4"):
            # print(bep.MessageCompression.Name(header.compression))
            uncompressed_len = struct.unpack("!I", data[0:4])[0]
            # print(data[4:])
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
        if (header.type == bep.MessageType.Value("PING")):
            print(packet)
            print(header_len)
            print(header)
            print(serial_len)
            print(message)
            print(serial)
        self.ssl_sock.send(packet)
        return

    def close(self):
        self.ssl_sock.close()
        return

    def receive_message(self):
        print("[BEP.V1]  Waiting for a message ...")

        # Header Length
        received = self.ssl_sock.recv(2)
        header_length = struct.unpack(">h", received)[0]

        # Header
        received = self.ssl_sock.recv(header_length)
        header = bep.Header()
        header.ParseFromString(received)

        # Message length
        received = self.ssl_sock.recv(4)
        message_length = struct.unpack(">i", received)[0]
        print("[BEP.V1] -> Message length : " + str(message_length))

        # Message
        received = self.ssl_sock.recv(message_length)

        if header.compression == bep.LZ4:
            # When the compression field is LZ4, the message consists of a 32 bit integer describing
            # the uncompressed message length followed by a single LZ4 block. After decompressing
            # the LZ4 block it should be interpreted as a protocol buffer message just as in the uncompressed case.
            uncompressed_message_length = struct.unpack(">i", received[0:4])[0]
            compressed_message = received[4:]
            print("[BEP.V1] -> Uncompressed message length : " + str(uncompressed_message_length))
            print("[BEP.V1] -> Decompress message ..")
            received = lz4.decompress(compressed_message, uncompressed_message_length)

        if header.type == bep.CLUSTER_CONFIG:
            # self.log("[BEP.V1] Received CLUSTER_CONFIG", Logger.INFO_ALL)
            message = bep.ClusterConfig()
            message.ParseFromString(received)
        elif header.type == bep.INDEX:
            # self.log("[BEP.V1] Received INDEX", Logger.INFO_ALL)
            message = bep.Index()
            message.ParseFromString(received)
        elif header.type == bep.INDEX_UPDATE:
            # self.log("[BEP.V1] Received INDEX_UPDATE", Logger.INFO_ALL)
            message = bep.Index()
            message.ParseFromString(received)
        elif header.type == bep.REQUEST:
            # self.log("[BEP.V1] Received REQUEST", Logger.INFO_ALL)
            message = bep.Request()
            message.ParseFromString(received)
        elif header.type == bep.RESPONSE:
            # self.log("[BEP.V1] Received RESPONSE", Logger.INFO_ALL)
            message = bep.Response()
            message.ParseFromString(received)
        elif header.type == bep.PING:
            # self.log("[BEP.V1] Received PING", Logger.INFO_ALL)
            message = bep.Ping()
            message.ParseFromString(received)
        elif header.type == bep.CLOSE:
            # self.log("[BEP.V1] Received CLOSE", Logger.INFO_ALL)
            message = bep.Close()
            message.ParseFromString(received)
        else:
            # self.log("[BEP.V1] Warning. Received UNKNOWN", Logger.WARNING)
            message = received

        return message
