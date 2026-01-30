import sys
sys.path.insert(1, '..')

import config
import hashlib
import multiprocessing
import random
import sqlite3
import string
import time
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

def _get_keys(db_file):
    con = sqlite3.connect(db_file)
    cur_get_keys = con.cursor()
    cur_get_keys.execute('SELECT data, name FROM keys')
    keys = [ row for row in cur_get_keys.fetchall() ]
    cur_get_keys.close()
    con.close()
    return keys

def resolve_by_packet(db_file, packet):
    keys = _get_keys(db_file)
    return utils.dissect.dissect(packet, keys)

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

# fill fields to have not been set earlier (db upgrade)
def update_fields(db_file):
    keys = _get_keys(db_file)

    con = sqlite3.connect(db_file)
    cur_put = con.cursor()
    cur_get = con.cursor()
    cur_get.execute('SELECT data, id FROM packets WHERE hop_count IS NULL OR payload_type IS NULL OR route_type IS NULL OR payload_text IS NULL OR ts_packet IS NULL')
    for row in cur_get.fetchall():
        d = utils.dissect.dissect(row[0], keys)
        hop_count = d.get_hop_count()
        if not hop_count is None:
            cur_put.execute('UPDATE packets SET hop_count=? WHERE id=?', (hop_count, row[1]))
        payload_type = d.get_payload_type()
        if not payload_type is None:
            cur_put.execute('UPDATE packets SET payload_type=? WHERE id=?', (payload_type, row[1]))
        route_type = d.get_route_type()
        if not route_type is None:
            cur_put.execute('UPDATE packets SET route_type=? WHERE id=?', (route_type, row[1]))
        ts_packet = d.get_timestamp()
        if not ts_packet is None:
            cur_put.execute('UPDATE packets SET ts_packet=? WHERE id=?', (ts_packet, row[1]))
        payload_text = d.get_payload_text()
        if not payload_text is None:
            cur_put.execute('UPDATE packets SET payload_text=? WHERE id=?', (payload_text, row[1]))
    cur_get.close()
    cur_put.close()
    con.commit()
    con.close()


def gen_channel_hash(name):
    return hashlib.sha256(name.encode('utf8')).digest()[0:16]


def add_channel(db_file, name):
    add_key(db_file, gen_channel_hash(name), name)


def gen_random_channel_name():
    n = random.randint(1, 9)
    # char_set = string.ascii_uppercase + string.ascii_lowercase + string.digits + '_-'
    char_set = string.ascii_lowercase
    return '#' + ''.join(random.sample(char_set * n, n))


# it is not realistic to use this implementation irl: too slow
def find_channel_names_worker(db_file):
    con = sqlite3.connect(db_file)

    while True:
        cur_get = con.cursor()
        cur_get.execute('SELECT data, id FROM packets WHERE channel IS NULL AND (payload_type=5 OR payload_type=6)')
        not_found_any = False
        for row in cur_get.fetchall():
            channel_name = gen_random_channel_name()
            key = gen_channel_hash(channel_name)
            d = utils.dissect.dissect(row[0], [(key, channel_name)])
            payload = d.get_payload()
            ts_packet = d.get_timestamp()
            txt_type = (payload[4] >> 2) if (len(payload) if not payload is None else 0) > 5 else -1
            if not payload is None and txt_type in (0x00, 0x01, 0x02) and ts_packet >= 2020:
                print(f'Found channel {channel_name}', payload)
                #add_key(db_file, key, channel_name)
                #break
            not_found_any = True

        cur_get.close()

        if not not_found_any:
            break

    con.close()

def find_channel_names_worker(db_file):
    con = sqlite3.connect(db_file)

    p_print = start = time.time()
    n_done = 0
    while True:
        cur_get = con.cursor()
        cur_get.execute('SELECT data, id FROM packets WHERE channel IS NULL AND (payload_type=5 OR payload_type=6) ORDER BY RANDOM()')
        not_found_any = True
        for row in cur_get.fetchall():
            print(row[1])
            for nr in range(26 ** 9):
                channel_name = '#'
                work_nr = nr
                while work_nr > 0:
                    channel_name += 'abcdefghijklmnopqrstuvwxyz'[work_nr % 26]
                    work_nr //= 26
                key = gen_channel_hash(channel_name)
                d = utils.dissect.dissect(row[0], [(key, channel_name)])
                payload = d.get_payload()
                ts_packet = d.get_timestamp()
                txt_type = (payload[4] >> 2) if (len(payload) if not payload is None else 0) > 5 else -1
                n_done += 1
                if not payload is None and txt_type in (0x00, 0x01, 0x02) and not ts_packet is None and ts_packet >= 2024:
                    print(f'Found channel {channel_name}', payload)
                    add_key(db_file, key, channel_name)
                    not_found_any = False
                    break
                now = time.time()
                if now - p_print >= 1:
                    p_print = now
                    print(n_done / (now - start), nr, channel_name)

        cur_get.close()

        if not not_found_any:
            break

    con.close()


def find_channel_names(db_file, process_count):
    handles = []
    for i in range(process_count):
        h = multiprocessing.Process(target=find_channel_names_worker, args=(db_file,))
        h.start()
        handles.append(h)

    for t in handles:
        t.join()


if __name__ == '__main__':
    #key = bytes([ 0x8b, 0x33, 0x87, 0xe9, 0xc5, 0xcd, 0xea, 0x6a, 0xc9, 0xe5, 0xed, 0xba, 0xa1, 0x15, 0xcd, 0x72 ])
    #add_key(config.db_file, key, 'Public')
    #add_channel(config.db_file, sys.argv[1])
    #update_fields(config.db_file)
    find_channel_names(config.db_file, int(sys.argv[1]))
