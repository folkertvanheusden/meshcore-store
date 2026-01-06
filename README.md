what it is
----------

This software curently listens for LoRa/MeshCore packets and stores them (partially decoded) in an sqlite3 database.
More functionality will be added later.


requirements
------------
An ESP32 (XIAO with SX1262, Heltec V3, T-Beam v1.2, Lilygo t3 or T-Beam supreme) and the platformio software.


installation
------------

### Python

```bash
python -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

### ESP32 module

* edit radio/config.h
* flash it:
```bash
cd radio
pio run -t upload -e X
```
X shall either `xiao_headers` (sx1262 via dupont cables), `xiao_connector` (the XIAO with the Wio-SX1262), `heltec_v3`, `t_beam_v1_2`, `lilygo_t3` or `t_beam_supreme`.


configuration
-------------

### ESP32 module

Connect to the WiFi station called "`MCWS-xxxxxx`" and configure its WiFi connection, that's it! (`xxxxxx` is the unique identifier of the ESP32 MCU, e.g. `MCWS-65763c`).

### Python

Edit config.py

Adding channels:

```bash
cd utils/
python resolver.py '#gouda'
```

Replace '#gouda' by whatever channel you would like to add. You need to explicitly configure each channel: this data cannot be determined automatically.


running
-------

* run the 'retriever:
```bash
cd retriever
python retriever.py
```

All data is stored in retriever/data.db (unless configured differently in config.py).

That's it for now!


querying the database
---------------------

* packets per date + hour
```sql
select strftime('%Y-%m-%d %H', ts) as `when`, count(*) from packets group by `when`;
```

* packets per hour
```sql
select strftime('%H', ts) as `when`, count(*) from packets group by `when`;
```

* packets per channel
```sql
select channel, count(*) from packets group by channel;
```

* packets per hop-count amount
```sql
select hop_count, count(*) from packets group by hop_count;
```

* packets per payload type
```sql
select payload_type, count(*) from packets group by payload_type;
```

* average time per hop
```sql
select avg(unixepoch(ts) - ts_packet) from packets where not ts_packet is null and unixepoch(ts) - ts_packet >= 0 and unixepoch(ts) - ts_packet < 255*2;
```
The `>= 0` and `< 255*2` is because for some devices the internal clock returns invalid time.

* how many packets were transmitted with a certain size
```sql
select length(data), count(*) from packets group by length(data);
```

* how much traffic per payload-type (2nd query is percentage of total)
```sql
select payload_type, sum(length(data)) from packets group by payload_type;
select payload_type, round(sum(length(data)) / CAST((SELECT SUM(LENGTH(data)) FROM packets) AS float) * 100, 2) from packets group by payload_type;
```


license
-------

MIT


written by
----------

Folkert van Heusden <folkert@vanheusden.com>
