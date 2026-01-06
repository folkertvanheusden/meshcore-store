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


license
-------

MIT


written by
----------

Folkert van Heusden <folkert@vanheusden.com>
