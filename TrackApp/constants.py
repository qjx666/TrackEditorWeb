"""CONSTANTS

Author: alguerre
License: MIT
"""
import datetime

# gpx file parser options
maximum_file_size = 10e+6
maximum_files = 5
valid_extensions = ['gpx']
default_datetime = datetime.datetime(2000, 1, 1, 0, 0, 0)
maximum_speed = 100  # km/h

# fix elevation
steep_distance = 0.2  # steep zone is always longer than X m
steep_gap = 0.6  # threshold to consider a steep zone in elevation
steep_k_moving_average = 20  # step for moving average if needed
fix_thr = 1000  # under 1000 points smoothing is used instead of fixing

# OSM request options
version = "v0.0"
email = "alguerre@outlook.com"
tool = "TrackEditor"

# gpx metadata
device = "Garmin Edge 830"
author_email = email
author_name = "Alonso Guarrior"
description = f"This activity has been updated with {tool} {version}"