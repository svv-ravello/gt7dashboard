# gt7dashboard

gt7dashboard is a live dashboard for Gran Turismo 7. Based on the recent discovery of the telemetry interface of GT7 described [here first](https://www.gtplanet.net/forum/threads/gt7-is-compatible-with-motion-rig.410728 ). This began as a fork of Bornhalls [gt7telemetry](https://github.com/Bornhall/gt7telemetry).

## Features

![image-20220816134448786](README.assets/screenshot.png)

* Time Diff Graph between Last Lap and Reference Lap
  * *Under dashed line* is better and *over dashed line* is worse than Reference Lap
  
* Speed/Distance Graph for Last Lap, Reference Lap and Median Lap.
  * Median Lap is calculated by the median of all recent laps
* Picker for Reference Lap
  * Default is Best Lap

* Throttle/Distance Graph
* Braking/Distance Graph
* Coasting/Distance Graph
* Race Line Graph
* Table of Speed Peaks and Valleys. Compared between reference and last lap
* Relative Fuel Map for choosing the right Fuel Map setting in order to reach distance, remaining time and desired lap times
* List off all recent laps with additional metrics, measured in percentage * 1000 for better readability
* Additional data for tuning such as Max Speed and Min Body Height
* Ability to Save current laps and reset all laps
* Additional "Race view" with only lap view and fuel map in a bigger font size
* Optional Brake Points (slow) when setting `GT7_ADD_BRAKEPOINTS=true`

## How to run

1. `pip3 install -r requirements.txt` to install Python dependencies (once)
2. `GT7_PLAYSTATION_IP=<CONSOLE IP ADDRESS> bokeh serve .` (when inside the folder)

## Docker

There is a `Dockerfile` available. This is a sample `docker-compose` configuration:

```yaml
    gt7dashboard:
        build:
            context: /home/user/work/gt7dashboard
        restart: unless-stopped
        container_name: gt7dashboard
        user: "1002"
        ports:
            - "5006:5006/tcp"
            - "33740:33740/udp"
        volumes:
            - /home/user/gt7data/:/usr/src/app/data
        environment:
            - BOKEH_ALLOW_WS_ORIGIN=domain_of_server:5006
            - GT7_PLAYSTATION_IP=<playstation ip>
            - TZ=Europe/Berlin
```



## Get Telemetry of a Demonstration lap or Replay

Replays and demonstrations will also output telemetry data. Start the replay or demonstration and enjoy the data.

Some demonstration data is cut short at the start. In the game this comes as a fast-forward effect at the start of the lap. Start the demonstration again, to get a proper lap.
