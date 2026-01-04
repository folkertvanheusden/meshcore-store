import sys
sys.path.insert(1, '..')

import config
import hashlib
import sqlite3
import utils.dissect


def _setup_db(db_file):
    con = sqlite3.connect(db_file)
    cur = con.cursor()
    try:
        cur.execute('PRAGMA journal_mode=wal')
        cur.execute('CREATE TABLE keys(data BLOB NOT NULL, name TEXT NOT NULL, PRIMARY KEY(data))')
        cur.execute('CREATE INDEX keys_name_idx ON keys(name)')
        cur.execute('CREATE INDEX packets_channel_idx ON packets(channel)')
        con.commit()
    except:
        pass
    cur.close()
    con.close()

def resolve_by_packet(db_file, packet):
    con = sqlite3.connect(db_file)
    cur_get_keys = con.cursor()
    cur_get_keys.execute('SELECT data, name FROM keys')
    keys = [ row for row in cur_get_keys.fetchall() ]
    cur_get_keys.close()
    con.close()
    d = utils.dissect.dissect(packet, keys)
    return d.get_channel()

def _resolve_by_channel(db_file, key, channel_name):
    con = sqlite3.connect(db_file)

    cur_put = con.cursor()
    cur_get = con.cursor()
    cur_get.execute('SELECT data, id FROM packets WHERE channel IS NULL')
    for row in cur_get.fetchall():
        d = utils.dissect.dissect(row[0], [(key, channel_name)])

        channel = d.get_channel()
        if channel == None:
            continue
        cur_put.execute('UPDATE packets SET channel=? WHERE id=?', (channel, row[1]))

    cur_get.close()
    cur_put.close()
    con.commit()
    con.close()

def add_key(db_file, key, name):
    _setup_db(db_file)

    con = sqlite3.connect(db_file)
    cur_put = con.cursor()
    cur_put.execute('INSERT INTO keys(data, name) VALUES(?, ?)', (key, name))
    cur_put.close()
    con.commit()
    con.close()

    _resolve_by_channel(db_file, key, name)

def add_channel(db_file, name):
    add_key(db_file, hashlib.sha256(name.encode('utf8')).digest()[0:16], name)

if __name__ == '__main__':
    #key = bytes([ 0x8b, 0x33, 0x87, 0xe9, 0xc5, 0xcd, 0xea, 0x6a, 0xc9, 0xe5, 0xed, 0xba, 0xa1, 0x15, 0xcd, 0x72 ])
    #add_key(config.db_file, key, 'Public')
    add_channel(config.db_file, sys.argv[1])
