#!/usr/bin/python3
from gevent import monkey
monkey.patch_all()

from threading import Thread
import time
from datetime import datetime
import logging
from flask import Flask, send_from_directory
from flask.ext.socketio import SocketIO, emit
import os
import fermenter

logging.basicConfig()

###############################################################################
# PARAMETERS
###############################################################################
STATS_INTERVAL = 2 # (sec): time to wait between updating stats
PLOTS_INTERVAL = 10 # (sec): time to wait between updating plots

###############################################################################
# GLOBALS
###############################################################################
app = Flask(__name__)
socketio = SocketIO(app)
threads = {}

###############################################################################
# EVENTS
###############################################################################
@socketio.on("socket event", namespace="/socket")
def handle_socket_event(message):
    print(message["data"])
@socketio.on("fermenter stop", namespace="/socket")
def handle_stop(message):
    if not events["fermenter idle"].is_set():
        events["fermenter idle"].set()
        fermenter.stop_fermenter(a, records, locks, events["fermenter idle"])
@socketio.on("fermenter start", namespace="/socket")
def handle_start(message):
    if events["fermenter idle"].is_set():
        events["fermenter idle"].clear()
        fermenter.start_fermenter(a, records, locks, events["fermenter idle"])
@socketio.on("impeller set", namespace="/socket")
def handle_impeller(message):
    with locks["records"]:
        if message["data"]:
            start = records["start"]
            if records["impeller"][-1] is None:
                records["impeller"].pop()
            records["impeller"].append((fermenter.hours_offset(start,
                                                               datetime.now()),
                                        records["impeller"][-1][1]))
            fermenter.set_impeller(a, locks["arduino"], float(message["data"]))
            records["impeller"].append((fermenter.hours_offset(start,
                                                               datetime.now()),
                                        float(message["data"])))
@socketio.on("recalibrate optics", namespace="/socket")
def handle_recalibrate(message):
    if not events["calibrate"].is_set():
        events["calibrate"].set()

###############################################################################
# THREADS
###############################################################################
def update_stats(records, locks):
    while True:
        with locks["records"]:
            stats = {
                "start": records["start"],
                "stop": records["stop"],
                "now": datetime.now(),
                "since": fermenter.hours_offset(records["start"],
                                                datetime.now()),
                "temp": records["temp"][-1],
                "heater": records["heater"][-1],
                "impeller": records["impeller"][-1],
                "optics": {
                    "calibration": {
                        "red": records["optics"]["calibration"]["red"],
                        "green": records["optics"]["calibration"]["green"],
                    },
                    "ambient": records["optics"]["ambient"][-1],
                    "red": records["optics"]["red"][-1],
                    "green": records["optics"]["green"][-1],
                },
            }
        socketio.emit("stats update", stats, namespace="/socket")
        time.sleep(STATS_INTERVAL)
def update_plots(records, locks):
    temp_last_update = None
    optics_last_update = None
    duty_cycles_last_update = None
    while True:
        rerender_optics = False
        rerender_temp = False
        rerender_duty_cycles = False
        with locks["records"]:
            start = records["start"]
            if records["optics"]["red"][-1]:
                if (not optics_last_update or
                        optics_last_update < records["optics"]["red"][-1][0]):
                    optics_last_update = records["optics"]["red"][-1][0]
                    rerender_optics = True
            if records["temp"][-1] and records["heater"][-1]:
                if (not temp_last_update or
                        temp_last_update < records["temp"][-1][0]):
                    temp_last_update = records["temp"][-1][0]
                    rerender_temp = True
            if records["impeller"][-1]:
                if (not duty_cycles_last_update or
                        duty_cycles_last_update < records["impeller"][-1][0]):
                    duty_cycles_last_update = records["impeller"][-1][0]
                    rerender_duty_cycles = True
                    if records["impeller"][-1] is None:
                        records["impeller"].pop()
                    records["impeller"].append((fermenter.hours_offset(start,
                                                                       datetime.now()),
                                                records["impeller"][-1][1]))
            if rerender_optics:
                socketio.emit("optics plot update", {
                    "calibration": records["optics"]["calibration"],
                    "redgreen": [x + (z,) for x, (y, z) in
                                 zip(records["optics"]["red"],
                                     records["optics"]["green"])],
                }, namespace="/socket")
                socketio.emit("environ plot update", {
                    "ambient": records["optics"]["ambient"]
                }, namespace="/socket")
            if rerender_temp:
                socketio.emit("temp plot update", {
                    "tempheater": [x + (z,) for x, (y, z) in
                                   zip(records["temp"], records["heater"])],
                }, namespace="/socket")
            if rerender_duty_cycles:
                socketio.emit("impeller plot update", {
                    "impeller": records["impeller"],
                }, namespace="/socket")
        time.sleep(PLOTS_INTERVAL)

###############################################################################
# ROUTES
###############################################################################
@app.route("/")
def index():
    """Deliver the dashboard"""
    global threads
    if "stats" not in threads.keys() or not threads["stats"].is_alive():
        threads["stats"] = Thread(target=update_stats, name="stats",
                                  args=(records, locks))
        threads["stats"].start()
    if "plot" not in threads.keys() or not threads["plot"].is_alive():
        threads["plots"] = Thread(target=update_plots, name="plots",
                                  args=(records, locks))
        threads["plots"].start()
    return send_from_directory("static", "dashboard.html")

@app.route("/client.js")
def client():
    """Deliver the client-side scripting"""
    return send_from_directory("static", "client.js")

@app.route("/style.css")
def style():
    """Deliver the client-side styling"""
    return send_from_directory("static", "style.css")

@app.route("/plots/<plot>")
def plots(plot):
    """Deliver the specified plot"""
    return send_from_directory("static/plots/", plot + ".svg")

###############################################################################
# MAIN
###############################################################################
if __name__ == "__main__":
    (a, records, locks, events, threads) = fermenter.run_fermenter()
    socketio.run(app, host='0.0.0.0', port=80)
