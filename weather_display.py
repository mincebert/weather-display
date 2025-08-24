# weather_display.py

__version__ = "0.2a1"

import network
from time import sleep
import machine
import re
import urequests
from picographics import PicoGraphics, DISPLAY_INKY_PACK
from pimoroni import Button

from WIFI_CONFIG import (SSID, PASSWORD)
from WEATHER_CONFIG import LATEST_URL


# interval between updates (s)
UPDATE_INTERVAL = 5

# maximum age for data before we warn that it's stuck (s)
MAX_AGE = 60 * 5    # = 5 minutes

# number of updates failed before warning
WARNING_FAIL_COUNT = 60 / UPDATE_INTERVAL * 5   # = 5 minutes

# temporary until handling multiple sensors
SENSOR_NAME = "Outside"

PEN_BLACK = 0
PEN_WHITE = 15

# number of seconds before restarting after an exception
RESTART_DELAY = 5

# return codes from get_weather()
ERROR_OK = 0
ERROR_SERVER = 1
ERROR_DATA = 2
ERROR_AGE = 3

# error messages for different types of error
ERROR_MSGS = {
    ERROR_SERVER: "Server not responding",
    ERROR_DATA: "No/incomplete data",
    ERROR_AGE: "Sensor data expired",
}

ERROR_UNKNOWN = "Error"

# buttons on display to pins
button_a = Button(12)
button_b = Button(13)
button_c = Button(14)


graphics = PicoGraphics(DISPLAY_INKY_PACK)
width, height = graphics.get_bounds()

graphics.set_update_speed(2)
graphics.set_font("sans")
graphics.set_thickness(2)


class Display:
    def __init__(self):
        super().__init__()
        self.clear()
        self._last_data = None

    def clear(self):
        self._data = {}

    def update(self):
        # abort if display is the same as last update()
        if (self._last_data is not None) and (self._data == self._last_data):
            print("Display same as last time - skip update")
            return

        # display has changed - render it and display

        graphics.set_pen(PEN_WHITE)
        graphics.clear()
        graphics.set_pen(PEN_BLACK)
        
        if "lines" in self._data:
            y = 12
            for s in self._data["lines"]:
                graphics.text(s, 0, y, scale=0.6)
                y += 22

        s = self._data.get("location")
        if s:
            graphics.set_thickness(2)
            graphics.text(s, 0, 12, scale=1.0)

        s = self._data.get("humidity")
        if s:
            graphics.set_thickness(2)
            graphics.text(s, 0, height - 20, scale=1.0)

        if self._data.get("temp"):
            num, degree, unit = self._data["temp"]
            graphics.set_thickness(4)
            # temp <num><o=degree><unit>
            graphics.text(num, 0, 64, scale=2.0)
            x = graphics.measure_text(num, scale=2.0)
            graphics.text(degree, x, 64 - 18, scale=1.0)
            x += graphics.measure_text(degree, scale=1.0)
            graphics.text(unit, x, 64, scale=2.0)

        s = self._data.get("time")
        if s:
            graphics.set_thickness(2)
            graphics.text(s, width - graphics.measure_text(s, scale=0.6), 12, scale=0.6)

        graphics.update()

        self._last_data = self._data

    def add_line(self, s):
        l = self._data.setdefault("lines", []).append(s)

    def set_location(self, s):
        self._data["location"] = s

    def set_humidity(self, s):
        self._data["humidity"] = s

    def set_temp(self, num, degree, unit):
        self._data["temp"] = (num, degree, unit)

    def set_time(self, t):
        self._data["time"] = t

display = Display()


def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    t = 0
    while wlan.isconnected() == False:
        print(f"Connecting to Wi-Fi ({t}s)...")
        sleep(1)
        t += 1
    print("Connected!", wlan.ifconfig())


def get_weather(sensor):
    # try to get the current weather from the server
    try:
        r = urequests.get(LATEST_URL)
    except OSError:
        print("Error connecting to server")
        return ERROR_SERVER
    data = r.json()
    #print(data)

    # look for the data for the required sensor
    try:
        d = data["sensors"][sensor]
    except KeyError:
        print("No or missing data")
        return ERROR_DATA
    print(data["datetime"], d)

    # try to find the required data for the sensor
    try:
        weather = { "temp": d["temp"], "humidity": d["humidity"] }
    except KeyError:
        print("Incomplete data")
        return ERROR_DATA

    # data is older than what is acceptable
    if d.get("age", 0) > MAX_AGE:
        print("Data has expired")
        return ERROR_AGE

    m = re.search("T(\d\d):(\d\d)", data["datetime"])
    hour, min = m.groups()

    # display the new weather
    display.clear()
    display.set_location(sensor)
    
    display.set_humidity("%d%% humidity" % d["humidity"])
    display.set_temp("%3.1f" % d["temp"], 'o', 'C')

    display.set_time(f"{hour}:{min}")
    display.update()

    return ERROR_OK


def display_error(e):
    "Display an error message."
    display.clear()
    display.add_line("ERROR!")
    display.add_line(e)
    display.update()


def main_loop():
    display.clear()

    display.add_line("WEATHER DISPLAY " + __version__)
    display.update()

    display.add_line("Connecting to Wi-Fi...")
    display.update()

    connect()

    display.add_line("Fetching weather...")
    display.update()

    try:
        count = 0
        fail_count = 0
        while True:
            print("Main loop interation %d" % count)

            if button_a.read() and button_c.read():
                print("Break using A+C.")
                break

            # try to get the weather
            status = get_weather(SENSOR_NAME)
            if status == ERROR_OK:
                # successful - reset failure count
                fail_count = 0

            elif status == ERROR_SERVER and fail_count < WARNING_FAIL_COUNT:
                # unable to connect to server and we aren't already at the
                # warning threshold - increase the failure count
                fail_count += 1

                # if we've now hit the warning threshold, display that
                if fail_count >= WARNING_FAIL_COUNT:
                    display_error(ERROR_MSGS[ERROR_SERVER])

            else:
                # some other type of error
                display_error(ERROR_MSGS.get(status, ERROR_UNKNOWN))

            sleep(UPDATE_INTERVAL)

            count += 1

    except KeyboardInterrupt:
        machine.reset()


print("*** WEATHER DISPLAY", __version__, "***")

# prevent startup if A+C are pressed
while not (button_a.read() and button_c.read()):
    try:
        main_loop()
    except Exception as e:
        print(f"Exception - restarting in {RESTART_DELAY}s...")
        print(str(e))

        display.clear()
        display.add_line(f"Exception - restarting in {RESTART_DELAY}s...")
        display.add_line(str(e))
        display.update()

        sleep(5)
else:
    print("Break using A+C.")

display.clear()
display.add_line("Stopped")
display.update()
