#! /usr/bin/env python

import sys
sys.path.insert(1, '..')

from websockets.sync.client import connect
import utils.resolver
import config
import sqlite3
import time


def setup_db(db_file):
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    try:
        cur.execute('PRAGMA journal_mode=wal')
        cur.execute('CREATE TABLE packets(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL, data BLOB NOT NULL, channel TEXT, hop_count INT, route_type INT, payload_type INT, ts_packet INT, payload_text TEXT)')
        cur.execute('CREATE TABLE meta_payload_type(type INTEGER NOT NULL, descr TEXT NOT NULL, PRIMARY KEY(type))')
        cur.execute('INSERT INTO meta_payload_type(type, descr) VALUES (0, "REQ"), (1, "RESPONSE"), (2, "TXT MSG"), (3, "ACK"), (4, "ADVERT"), (5, "GRP_TXT"), (6, "GRP_DATA"), (7, "ANON_REQ"), (8, "PATH"), (9, "TRACE"), (10, "MULTIPART"), (11, "CONTROL"), (12, "reserved 0x0c"), (13, "reserved 0x0d"), (14, "reserved 0x0e"), (15, "RAW_CUSTOM")')
        con.commit()
    except:
        pass
    cur.close()
    con.close()

def worker(address, db_file):
    while True:
        try:
            con = sqlite3.connect(db_file)

            uri = f'ws://{address}/ws'
            print(f'{time.ctime()} (re-)connecting to {uri}')
            with connect(uri) as websocket:
                print(f'{time.ctime()} connected')
                while True:
                    packet = websocket.recv()
                    if packet == None:
                        break

                    cur = con.cursor()
                    try:
                        d = utils.resolver.resolve_by_packet(db_file, packet)
                        channel = d.get_channel() if d else None
                        hop_count = d.get_hop_count()
                        payload_type = d.get_payload_type()
                        route_type = d.get_route_type()
                        ts_packet = d.get_timestamp()
                        payload_text = d.get_payload_text()

                        print(f'{time.ctime()} packet for {"-" if channel is None else channel} ({payload_text})')

                        cur.execute('INSERT INTO packets(data, channel, hop_count, payload_type, route_type, ts_packet, payload_text) VALUES(?, ?, ?, ?, ?, ?, ?)', (packet, channel, hop_count, payload_type, route_type, ts_packet, payload_text))
                        con.commit()
                    except Exception as e:
                        print(f'Failed inserting packet: {e}')
                    cur.close()

        except Exception as e:
            print(f'{time.ctime()} worker: {e}')
            time.sleep(0.1)  # prevent busy loop

    con.close()

if __name__ == "__main__":
    setup_db(config.db_file)
    worker(config.radio_hostname, config.db_file)
