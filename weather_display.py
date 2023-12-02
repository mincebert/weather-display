# weather_display.py

__version__ = "0.1a2"

import network
from time import sleep
import machine
import urequests
import json
from picographics import PicoGraphics, DISPLAY_INKY_PACK
from pimoroni import Button

from WIFI_CONFIG import (SSID, PASSWORD)
from WEATHER_CONFIG import LATEST_URL

UPDATE_INTERVAL = 5		# number of seconds between updates
WARNING_FAIL_COUNT = 60 / UPDATE_INTERVAL * 5		# number of updates failed before warning

SENSOR_NAME = "Outside"		# temporary until handling multiple sensors

PEN_BLACK = 0
PEN_WHITE = 15


button_a = Button(12)
button_b = Button(13)
button_c = Button(14)


graphics = PicoGraphics(DISPLAY_INKY_PACK)
width, height = graphics.get_bounds()
graphics.set_update_speed(2)

last_weather = None

def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    while wlan.isconnected() == False:
        print("Waiting for wi-fi connection...")
        sleep(1)
    print("Connected!", wlan.ifconfig())

def screen_clear():
    graphics.set_pen(PEN_WHITE)
    graphics.clear()
    graphics.set_pen(PEN_BLACK)

def get_weather(sensor):
    global last_weather
    try:
        r = urequests.get(LATEST_URL)
    except OSError:
        print("Error connecting to server")
        return
    data = r.json()
    #print(data)
    try:
        d = data["sensors"][sensor]
    except KeyError:
        print("No or missing data")
        return False
    print(d)
    try:
        new_weather = { "temp": d["temp"], "humidity": d["humidity"] }
    except KeyError:
        print("Incomplete data")
        return False

    if last_weather == new_weather:
        print("Same as last - no update")
        return True

    screen_clear()
    graphics.set_font("sans")
    graphics.set_thickness(2)
    graphics.text(sensor, 0, 12, scale=1.0)
    graphics.text("%d%% humidity" % d["humidity"], 0, height - 20, scale=1.0)
    graphics.set_thickness(4)
    # temp
    t = "%3.1f" % d["temp"]
    graphics.text(t, 0, 64, scale=2.0)
    x = graphics.measure_text(t, scale=2.0)
    t = "o"
    graphics.text(t, x, 64 - 18, scale=1.0)
    x += graphics.measure_text(t, scale=1.0)
    graphics.text("C", x, 64, scale=2.0)
    graphics.update()
    last_weather = new_weather
    return True

screen_clear()
graphics.set_font("sans")
graphics.set_thickness(2)

try:
    graphics.text("WEATHER DISPLAY " + __version__, 0, 12, scale=0.6)
    graphics.text("Connecting to Wi-Fi...", 0, 34, scale=0.6)
    graphics.update()
    connect()
    graphics.text("Fetching weather...", 0, 56, scale=0.6)
    graphics.update()

    count = 0
    fail_count = 0
    while True:
        print("Main loop interation %d" % count)

        if button_a.read() and button_c.read():
            print("Break using A+C.")
            break

        if get_weather(SENSOR_NAME):
            fail_count = 0
        elif fail_count < WARNING_FAIL_COUNT:
            fail_count += 1
            if fail_count >= WARNING_FAIL_COUNT:
                graphics.text("<!>", 240, 14, scale=1.0)
                graphics.update()

        sleep(UPDATE_INTERVAL)

        count += 1

except KeyboardInterrupt:
    machine.reset()

screen_clear()
graphics.set_thickness(2)
graphics.text("Break.", 0, 12, scale=0.6)
graphics.update()
