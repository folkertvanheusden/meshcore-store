import config
import dissect
import sqlite3


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

def _resolver(db_file, key, channel_name):
    con = sqlite3.connect(db_file)

    keys = []
    cur_get_keys = con.cursor()
    cur_get_keys.execute('SELECT data FROM keys')
    keys = [ row[0] for row in cur_get_keys.fetchall() ]
    cur_get_keys.close()

    cur_put = con.cursor()
    cur_get = con.cursor()
    cur_get.execute('SELECT data, id FROM packets WHERE channel IS NULL')
    for row in cur_get.fetchall():
        d = dissect.dissect(row[0], [(key, channel_name)])

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
    con.close()

    _resolver(db_file, key, name)

if __name__ == '__main__':
    key = bytes([ 0x8b, 0x33, 0x87, 0xe9, 0xc5, 0xcd, 0xea, 0x6a, 0xc9, 0xe5, 0xed, 0xba, 0xa1, 0x15, 0xcd, 0x72 ])
    add_key(config.db_file, key, 'Public')
