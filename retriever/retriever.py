#! /usr/bin/env python

from websockets.sync.client import connect
import config
import sqlite3


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
            with connect(uri) as websocket:
                while True:
                    packet = websocket.recv()
                    if packet == None:
                        break

                    cur = con.cursor()
                    try:
                        cur.execute('INSERT INTO packets(data) VALUES(?)', (packet,))
                        con.commit()
                    except Exception as e:
                        print(f'Failed inserting packet: {e}')
                    cur.close()

        except TimeoutError:
            pass

        except Exception as e:
            print(f'worker: {e}')
            raise e

    con.close()

if __name__ == "__main__":
    setup_db(config.db_file)
    worker(config.radio_hostname, config.db_file)
