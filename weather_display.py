# weather_display.py

__version__ = "0.1a3"

import network
from time import sleep
import machine
import urequests
from picographics import PicoGraphics, DISPLAY_INKY_PACK
from pimoroni import Button

from WIFI_CONFIG import (SSID, PASSWORD)
from WEATHER_CONFIG import LATEST_URL


# interval between updates (s)
UPDATE_INTERVAL = 5

# maximum age for data before we warn that it's stuck (s)
MAX_AGE = 60 * 5    # 5 minutes

# number of updates failed before warning
WARNING_FAIL_COUNT = 60 / UPDATE_INTERVAL * 5   # 5 minutes

# temporary until handling multiple sensors
SENSOR_NAME = "Outside"

PEN_BLACK = 0
PEN_WHITE = 15

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

    # try to get the current weather from the server
    try:
        r = urequests.get(LATEST_URL)
    except OSError:
        print("Error connecting to server")
        last_weather = None
        return ERROR_SERVER
    data = r.json()
    #print(data)

    # look for the data for the required sensor
    try:
        d = data["sensors"][sensor]
    except KeyError:
        print("No or missing data")
        last_weather = None
        return ERROR_DATA
    print(d)

    # try to find the required data for the sensor
    try:
        new_weather = { "temp": d["temp"], "humidity": d["humidity"] }
    except KeyError:
        print("Incomplete data")
        last_weather = None
        return ERROR_DATA

    # data is older than what is acceptable
    if d.get("age", 0) > MAX_AGE:
        print("Data has expired")
        last_weather = None
        return ERROR_AGE

    if last_weather == new_weather:
        print("Same as last - no update")
        return ERROR_OK

    # display the new weather
    screen_clear()
    graphics.set_thickness(2)
    graphics.text(sensor, 0, 12, scale=1.0)
    graphics.text(
        "%d%% humidity" % d["humidity"], 0, height - 20, scale=1.0)
    graphics.set_thickness(4)
    # temp <num><o=degree>C
    t = "%3.1f" % d["temp"]
    graphics.text(t, 0, 64, scale=2.0)
    x = graphics.measure_text(t, scale=2.0)
    t = "o"
    graphics.text(t, x, 64 - 18, scale=1.0)
    x += graphics.measure_text(t, scale=1.0)
    graphics.text("C", x, 64, scale=2.0)
    graphics.update()
    last_weather = new_weather
    return ERROR_OK


def display_error(e):
    "Display an error message."
    screen_clear()
    graphics.set_thickness(4)
    graphics.text("ERROR!", 0, 14, scale=1.0)
    graphics.set_thickness(2)
    graphics.text(e, 0, 50, scale=0.8)
    graphics.update()


print("*** WEATHER DISPLAY", __version__, "***")

screen_clear()
graphics.set_font("sans")
graphics.set_thickness(2)

try:
    # display boot up messages
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

screen_clear()
graphics.set_thickness(2)
graphics.text("Break.", 0, 12, scale=0.6)
graphics.update()
