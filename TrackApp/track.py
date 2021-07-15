"""TRACK
The track class defines how the loaded GPX files are internally represented.
Each of them is loaded in one Track object as a segment. It includes methods
to manipulate these segments. From the user perspective, this manipulation is
carried out througout the Edit Menu.

Author: alguerre
License: MIT
"""
import datetime as dt
import pandas as pd
import numpy as np
import geopy.distance
import gpxpy.gpx
import time

from . import gpx
from . import constants as c


class Track:
    """
    This class is designed to store gpx like data consisting of latitude-
    longitude-elevation-time and manipulate them. All these operations are
    done with pandas.
    The data representation is:
        - A pandas dataframe stores all data
        - segments: each compoment of the track, each gpx file is a segment
        - The dataframe have some extra columns not from gpx file, like
        cumulated distance or elevation.
        - Properties to store overall information
    """
    def __init__(self):
        # Define dataframe and types
        self.columns = ['lat', 'lon', 'ele', 'segment', 'time']
        self.df_track = pd.DataFrame(columns=self.columns)
        self._force_columns_type()

        # General purpose properties
        self.size = 0  # number of gpx in track
        self.last_segment_idx = 0
        self.extremes = (0, 0, 0, 0)  # lat min, lat max, lon min, lon max
        self.total_distance = 0
        self.total_uphill = 0
        self.total_downhill = 0
        self.selected_segment = []  # line object from matplotlib
        self.selected_segment_idx = []  # index of the segment

    def add_gpx(self, file: str):
        gpx_track = gpx.Gpx(file)
        df_gpx = gpx_track.to_pandas()
        df_gpx = df_gpx[self.columns]
        self.size += 1
        self.last_segment_idx += 1
        df_gpx['segment'] = self.last_segment_idx

        self.df_track = pd.concat([self.df_track, df_gpx])
        self.df_track = self.df_track.reset_index(drop=True)
        self._update_summary()  # for full track
        self._force_columns_type()

    def get_segment(self, index: int):
        return self.df_track[self.df_track['segment'] == index]

    def reverse_segment(self, index: int):
        segment = self.get_segment(index)
        time = self.df_track.time  # using time is problematic, is managed
        # separately
        segment = segment.drop(columns=['time'])

        rev_segment = pd.DataFrame(segment.values[::-1],
                                   segment.index,
                                   segment.columns)
        rev_segment['time'] = time[::-1]
        self.df_track.loc[self.df_track['segment'] == index] = rev_segment
        self._force_columns_type()  # ensure proper type for columns

        self._update_summary()  # for full track

    def _get_speed_factor_to_slope(self, slope: float) -> float:
        """
        Get a speed factor to compensate the mean speed with slope effects.
        Uphill the speed is reduced up to 1/3 when slope is -20%.
        Downhill the speed is increased up to 3 times when slops is +20%.
        The equation has been got using the matlab fitting tool in the set of
        inputs values:
        Flat terrain: x = linspace(-0.5, 0.5, 10);
                      y = linspace(1.05, 0.95, 10);
        Uphill terrain: x = linspace(-18, -20, 10);
                        y = linspace(2.8, 3.0, 10);
        Downhill terrain: x = linspace(18, 20, 10);
                          y = linspace(1/2.8, 1/3, 10);
        Formula to express slope in %:
            angle % = tan(angle) * 100%

        :param slope: in %
        :return: speed factor
        """

        a = 1.005
        b = -0.05725
        c = -1.352e-8
        d = 0.8164

        if slope < 0:
            b = -0.07  # accelerate the model when downhill

        if slope > 17.8:  # at this point the speed is x1/3
            speed_factor = 1 / 3
        elif slope < -15.9:    # at this point the speed is x3
            speed_factor = 3
        else:
            speed_factor = a * np.exp(b * slope) + c * np.exp(d * slope)

        return speed_factor

    def insert_timestamp(self, initial_time: dt.datetime,
                         desired_speed: float,
                         consider_elevation: bool = False):
        if not consider_elevation:
            self.df_track['time'] = \
                self.df_track.apply(
                    lambda row:
                    initial_time + dt.timedelta(hours=row['distance']/desired_speed),
                    axis=1)
        else:
            ele_diff = np.diff(self.df_track['ele'].values)
            dist_diff = np.diff(self.df_track['distance'].values)

            # Remove 0 diff distances, not moving
            self.df_track = self.df_track[np.append(dist_diff != 0, True)]
            ele_diff = ele_diff[dist_diff != 0]
            dist_diff = dist_diff[dist_diff != 0]

            slope = np.tan(np.arcsin(1e-3 * ele_diff/dist_diff)) * 100
            slope -= np.mean(slope)  # when mean slope mean speed
            speed_factor = np.array(
                list(map(self._get_speed_factor_to_slope, slope))
            )
            speed_elevation = desired_speed * speed_factor

            used_time = 0
            start = time.time()
            avg_speed = desired_speed * 10

            while abs(avg_speed - desired_speed) > 0.05 * desired_speed and \
                    used_time < 0.5:
                time_delta = dist_diff / speed_elevation
                avg_speed = sum(dist_diff)/sum(time_delta)
                speed_elevation -= avg_speed - desired_speed
                used_time = time.time() - start

            relative_time = np.append(0, np.cumsum(time_delta))
            self.df_track['relative_time'] = relative_time
            self.df_track['time'] = \
                self.df_track.apply(
                    lambda row:
                    initial_time + dt.timedelta(hours=row['relative_time']),
                    axis=1)

    def save_gpx(self, gpx_filename: str):
        # Create track
        ob_gpxpy = gpxpy.gpx.GPX()
        gpx_track = gpxpy.gpx.GPXTrack()
        ob_gpxpy.tracks.append(gpx_track)

        # Insert default metadata
        ob_gpxpy.creator = c.device
        ob_gpxpy.author_email = c.author_email
        ob_gpxpy.description = c.description
        ob_gpxpy.author_name = c.author_name

        # Create segments in track
        for seg_id in self.df_track.segment.unique():
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)

            df_segment = self.get_segment(seg_id)

            # Insert points to segment
            for idx in df_segment.index:
                latitude = df_segment.loc[idx, 'lat']
                longitude = df_segment.loc[idx, 'lon']
                elevation = df_segment.loc[idx, 'ele']
                time = df_segment.loc[idx, 'time']
                gpx_point = gpxpy.gpx.GPXTrackPoint(latitude, longitude,
                                                    elevation=elevation,
                                                    time=time)
                gpx_segment.points.append(gpx_point)

        # Write file
        with open(gpx_filename, 'w') as f:
            f.write(ob_gpxpy.to_xml())

    def smooth_elevation(self, index: int):
        # Apply moving average to fix elevation

        df_segment = self.get_segment(index)
        elevation = df_segment.ele.to_numpy()

        # Moving average
        n = int(np.ceil(df_segment.shape[0]*0.05))
        elevation_ma = self._moving_average(elevation, n)

        # Concatenate moving average and initial line
        smooth_elevation = np.concatenate(
            (np.array([elevation[0] + i*(elevation_ma[0]-elevation[0])/n
                       for i in range(1, n)]),
             elevation_ma)
        )

        # Insert new elevation in track
        df_segment = df_segment.drop(columns=['ele'])
        df_segment['ele'] = smooth_elevation
        self.df_track.loc[self.df_track['segment'] == index] = df_segment

    def fix_elevation(self, index: int):
        df_segment = self.get_segment(index)

        # Identify and remove steep zones
        steep_zone = [False] * df_segment.shape[0]
        last_steep = 0

        for i, (e, d) in enumerate(zip(df_segment['ele'].diff(),
                                       df_segment['distance'])):
            if abs(e) > c.steep_gap:
                steep_zone[i] = True
                last_steep = d

            elif d - last_steep < c.steep_distance:
                if d > c.steep_distance:
                    steep_zone[i] = True

        df_segment['steep_zone'] = steep_zone
        df_no_steep = df_segment.copy()
        df_no_steep['ele_to_fix'] = np.where(df_segment['steep_zone'] == False,
                                             df_segment['ele'], -1)

        # Fill steep zones
        fixed_elevation = df_no_steep['ele_to_fix'].copy().to_numpy()
        original_elevation = df_no_steep['ele'].copy().to_numpy()
        fixed_steep_zone = df_no_steep['steep_zone'].copy()
        before_x = before_y = after_x = after_y = None

        for i in range(1, len(fixed_elevation)):
            if not df_no_steep['steep_zone'].loc[i - 1] and \
                    df_no_steep['steep_zone'].loc[i]:
                before_x = np.arange(i - 11, i - 1)
                before_y = fixed_elevation[i - 11:i - 1]
                after_x = None
                after_y = None

            if df_no_steep['steep_zone'].loc[i - 1] and not \
                    df_no_steep['steep_zone'].loc[i]:
                after_x = np.arange(i, i + 10)
                after_y = fixed_elevation[i:i + 10]
                coef = np.polyfit(np.concatenate((before_x, after_x)),
                                  np.concatenate((before_y, after_y)),
                                  3)
                for i in range(before_x[-1], after_x[0]):
                    fixed_elevation[i] = np.polyval(coef, i)
                    fixed_steep_zone[i] = False

        # Apply moving average on tail
        if after_y is None and after_x is None:
            n = c.steep_k_moving_average
            fixed_elevation[before_x[-1]:] = np.concatenate((
                original_elevation[before_x[-1]:before_x[-1] + n - 1],
                self._moving_average(original_elevation[before_x[-1]:], n)))
            fixed_steep_zone[before_x[-1]:] = True

        # Insert new elevation in track
        df_segment['ele'] = fixed_elevation
        self.df_track.loc[self.df_track['segment'] == index] = df_segment

    def remove_segment(self, index: int):
        # Drop rows in dataframe
        idx_segment = self.df_track[(self.df_track['segment'] == index)].index
        self.df_track = self.df_track.drop(idx_segment)
        self.df_track = self.df_track.reset_index(drop=True)
        self.size -= 1

        # Update metadata
        self._update_summary()

        # Clean full track if needed
        if self.size == 0:
            self.df_track = self.df_track.drop(self.df_track.index)

        return self.size

    def divide_segment(self, div_index: int):
        """
        :param div_index: refers to the index of the full df_track, not segment
        """
        self.df_track['index'] = self.df_track.index

        def segment_index_modifier(row):
            if row['index'] < div_index:
                return row['segment']
            else:
                return row['segment'] + 1

        self.df_track['segment'] = \
            self.df_track.apply(lambda row: segment_index_modifier(row),
                                axis=1)

        self.df_track = self.df_track.drop(['index'], axis=1)
        self.size += 1
        self.last_segment_idx = max(self.df_track['segment'])

        return True

    def change_order(self, new_order: dict):
        self.df_track.segment = self.df_track.apply(
            lambda row: new_order[row.segment],
            axis=1)

        self.df_track['index1'] = self.df_track.index
        self.df_track = self.df_track.sort_values(by=['segment', 'index1'])
        self.df_track = self.df_track.drop(labels=['index1'], axis=1)
        self.df_track = self.df_track.reset_index(drop=True)
        self._update_summary()  # for full track

    def _moving_average(self, a, n: int = 3):
        """
        Naive moving average implementation
        :param a: numpy array
        :param n: point mean values
        :return: smooth numpy array
        """
        ret = np.cumsum(a, dtype=float)
        ret[n:] = ret[n:] - ret[:-n]
        return ret[n - 1:] / n

    def _update_summary(self):
        self._insert_positive_elevation()
        self._insert_negative_elevation()
        self._insert_distance()
        self._update_extremes()
        self.total_distance = self.df_track.distance.iloc[-1]
        self.total_uphill = self.df_track.ele_pos_cum.iloc[-1]
        self.total_downhill = self.df_track.ele_neg_cum.iloc[-1]

    def _force_columns_type(self):
        # At some points it is needed to ensure the data type of each column
        self.df_track['lat'] = self.df_track['lat'].astype('float32')
        self.df_track['lon'] = self.df_track['lon'].astype('float32')
        self.df_track['ele'] = self.df_track['ele'].astype('float32')
        self.df_track['segment'] = self.df_track['segment'].astype('int32')
        self.df_track['time'] = self.df_track['time'].astype('datetime64[ns]')

    def _insert_positive_elevation(self):
        self.df_track['ele diff'] = self.df_track['ele'].diff()
        negative_gain = self.df_track['ele diff'] < 0
        self.df_track.loc[negative_gain, 'ele diff'] = 0

        # Define new column
        self.df_track['ele_pos_cum'] = \
            self.df_track['ele diff'].cumsum().astype('float32')

        # Drop temporary columns
        self.df_track = self.df_track.drop(labels=['ele diff'], axis=1)

    def _insert_negative_elevation(self):
        self.df_track['ele diff'] = self.df_track['ele'].diff()
        negative_gain = self.df_track['ele diff'] > 0
        self.df_track.loc[negative_gain, 'ele diff'] = 0

        # Define new column
        self.df_track['ele_neg_cum'] = \
            self.df_track['ele diff'].cumsum().astype('float32')

        # Drop temporary columns
        self.df_track = self.df_track.drop(labels=['ele diff'], axis=1)

    def _insert_distance(self):
        # Shift latitude and longitude (such way that first point is 0km)
        self.df_track['lat_shift'] = pd.concat(
            [pd.Series(np.nan), self.df_track.lat[0:-1]]). \
            reset_index(drop=True)
        self.df_track['lon_shift'] = pd.concat(
            [pd.Series(np.nan), self.df_track.lon[0:-1]]). \
            reset_index(drop=True)

        def compute_distance(row):
            from_coor = (row.lat, row.lon)
            to_coor = (row.lat_shift, row.lon_shift)
            try:
                return abs(geopy.distance.geodesic(from_coor, to_coor).km)
            except ValueError:
                return 0

        # Define new columns
        self.df_track['p2p_distance'] = self.df_track.apply(compute_distance,
                                                            axis=1)
        self.df_track['distance'] = \
            self.df_track.p2p_distance.cumsum().astype('float32')

        # Drop temporary columns
        self.df_track = self.df_track.drop(
            labels=['lat_shift', 'lon_shift', 'p2p_distance'], axis=1)

    def _update_extremes(self):
        self.extremes = \
            (self.df_track["lat"].min(), self.df_track["lat"].max(),
             self.df_track["lon"].min(), self.df_track["lon"].max())