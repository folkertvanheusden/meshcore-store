from Crypto.Cipher import AES
import hashlib
import hmac


class dissect:
    PAYLOAD_TYPE_REQ = 0x00
    PAYLOAD_TYPE_RESPONSE = 0x01
    PAYLOAD_TYPE_TXT_MSG = 0x02
    PAYLOAD_TYPE_ACK = 0x03
    PAYLOAD_TYPE_ADVERT = 0x04
    PAYLOAD_TYPE_GRP_TXT = 0x05
    PAYLOAD_TYPE_GRP_DATA = 0x06
    PAYLOAD_TYPE_ANON_REQ = 0x07
    PAYLOAD_TYPE_PATH = 0x08
    PAYLOAD_TYPE_TRACE = 0x09
    PAYLOAD_TYPE_MULTIPART = 0x0a
    PAYLOAD_TYPE_CONTROL = 0x0b
    PAYLOAD_TYPE_RAW_CUSTOM	= 0x0f

    def __init__(self, packet, keys):
        self._channel = None
        self._path = None

        try:
            header = packet[0]
            route_type = header & 3
            payload_type = (header >> 2) & 15
            payload_version = header >> 6

            offset = 1
            if route_type == 0 or route_type == 3:
                transport_codes1 = (packet[1] << 8) | packet[2]
                transport_codes2 = (packet[3] << 8) | packet[4]
                offset += 4

            path_len = packet[offset]
            offset += 1
            self._path = [ node for node in packet[offset: offset + path_len] ]
            offset += path_len

            if payload_type in (self.PAYLOAD_TYPE_ADVERT,):
                self._channel = ''
            elif payload_type in (self.PAYLOAD_TYPE_GRP_TXT, self.PAYLOAD_TYPE_GRP_DATA):
                channel_hash = packet[offset]
                offset += 1
                cipher_mac = (packet[offset] << 8) | packet[offset + 1]
                offset += 2
                cipher_text = packet[offset:]

                for key in keys:
                    if self._try_key(cipher_text, key[0], cipher_mac):
                        self._channel = key[1]
                        self._payload = self._decrypt(cipher_text, key[0])
                        break

        except Exception as e:
            print(f'Packet is invalid: {e} {e.__traceback__.tb_lineno}')

    def _try_key(self, data, key, digest_mac_in):
        signature = hmac.new(key, msg=data, digestmod=hashlib.sha256).digest()
        digest_mac = (signature[0] << 8) | signature[1]
        return digest_mac == digest_mac_in

    def _decrypt(self, data, key):
        cipher = AES.new(key, AES.MODE_ECB)
        return cipher.decrypt(data)[0:len(data)]

    def get_channel(self):
        return self._channel

    def get_hop_count(self):
        return len(self._path) if self._path else None

    def get_path(self):
        return self._path

if __name__ == '__main__':
    # key = bytes([ 0x8b, 0x33, 0x87, 0xe9, 0xc5, 0xcd, 0xea, 0x6a, 0xc9, 0xe5, 0xed, 0xba, 0xa1, 0x15, 0xcd, 0x72 ])
    # channel_name = 'Public'
    # data = bytes([ ])
    # print(dissect(data, [(key, channel_name)]).get_channel())
    pass
