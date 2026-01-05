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
        cur.execute('CREATE TABLE packets(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL, data BLOB NOT NULL, channel TEXT)')
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

                    channel = utils.resolver.resolve_by_packet(db_file, packet)
                    print(f'{time.ctime()} packet for {"-" if channel is None else channel}')

                    cur = con.cursor()
                    try:
                        if not channel is None:
                            cur.execute('INSERT INTO packets(data, channel) VALUES(?, ?)', (packet, channel))
                        else:
                            cur.execute('INSERT INTO packets(data) VALUES(?)', (packet,))
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
