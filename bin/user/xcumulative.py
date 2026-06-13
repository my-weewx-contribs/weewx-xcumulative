# -*- coding: utf-8 -*-
"""
xcumulative.py

A WeeWX XType to produce cumulative series data with user specified reset times.

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public Licence as published by the Free Software
Foundation; either version 3 of the Licence, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public Licence for more details.

Version: 0.3.0b2                                        Date: ? June 2026

Revision History
    ? June 2026         v0.3.0
        -   complete revision
    25 October 2022     v0.2.0
        -   implement support for zero_lead_in
    23 October 2022     v0.1.0
        -   initial release

--------------------------------------------------------------------------------
Description

The cumulative series is derived by obtaining a 'sum' aggregate series for the
obs type concerned. A running total is maintained for the resulting series data
with the running total increment by the aggregate vale for each interval. The
running total at the end of an interval is used as the cumulative value for
that interval. Timestamp values in the resulting series are as per standard
WeeWX XType series.

As an example, if the archive contains the following data (human-readable
date-time shown for clarity):

    dateTime                                rain
    1641649500(2022-01-08 23:45:00 AEST)    0.0
    1641649800(2022-01-08 23:50:00 AEST)    1.0
    1641650100(2022-01-08 23:55:00 AEST)    0.0
    1641650400(2022-01-09 00:00:00 AEST)    0.6
    1641650700(2022-01-09 00:05:00 AEST)    1.8
    1641651000(2022-01-09 00:10:00 AEST)    0.0
    1641651300(2022-01-09 00:15:00 AEST)    0.4
    1641651600(2022-01-09 00:20:00 AEST)    0.0
    1641651900(2022-01-09 00:25:00 AEST)    0.0
    1641652200(2022-01-09 00:30:00 AEST)    0.4

The resulting cumulative series would be:
    [[1641649200, 1641649500, 0.0], [1641649500, 1641649800, 1.0],
     [1641649800, 1641650100, 1.0], [1641650100, 1641650400, 1.6],
     [1641650400, 1641650700, 3.4], [1641650700, 1641651000, 3.4],
     [1641651000, 1641651300, 3.8], [1641651300, 1641651600, 3.8],
     [1641651600, 1641651900, 3.8], [1641651900, 1641652200, 4.2]]

If a reset time of 00:00 was specified the resulting cumulative series would
be:
    [[1641649200, 1641649500, 0.0], [1641649500, 1641649800, 1.0],
     [1641649800, 1641650100, 1.0], [1641650100, 1641650400, 1.6],
     [1641650400, 1641650700, 1.8], [1641650700, 1641651000, 1.8],
     [1641651000, 1641651300, 2.2], [1641651300, 1641651600, 2.2],
     [1641651600, 1641651900, 2.2], [1641651900, 1641652200, 2.6]]

A resettable cumulative series XType is useful for producing plots of
cumulative data that resets at a give time, eg plotting daily energy values or
daily rainfall to/from 9am. In such cases, the WeeWX plot definition needs to
use the aggregate 'cumulative' with an appropriate 'reset' option for the obs
type concerned. As an example, to produce a day plot of cumulative rainfall
that resets at 9am daily the following plot definition could be used:

    [[[dayrain]]]
        plot_type = line
        [[[[rain]]]]
            aggregate_type = cumulative
            aggregate_interval = 300
            reset = 09:00
            label = Rain (daily total)
"""

# python imports
from __future__ import absolute_import
import datetime
import logging
import time

# WeeWX imports
import weewx
import weeutil.weeutil
import weewx.engine
import weewx.xtypes

# we require WeeWX 4.6.0 or later so we can safely only support WeeWX 4 logging
log = logging.getLogger(__name__)
# our version number
XCUMULATIVE_VERSION = '0.3.0b2'


# ==============================================================================
#                              Class XCumulative
# ==============================================================================

class XCumulative(weewx.xtypes.XType):
    """XType to produce cumulative series data with user specified reset times."""

    # define a some reset time synonyms
    reset_defs = {'midnight': '00:00',
                  'midday': '12:00',
                  'day': '00:00',
                  'month': '1T00:00',
                  'year': '01-01T00:00'}

    def __init__(self):
        pass

    def get_series(self, obs_type, timespan, db_manager, aggregate_type=None,
                   aggregate_interval=None, **option_dict):
        """Obtain a cumulative series with a user specified reset time.

        The following options are supported in option_dict:

        reset: Date-time specification for cumulative value reset times.
               Optional string. Format is [mm-][dd][T]HH:MM or one of
               ('midnight', 'midday', 'day', 'month', 'year'). Default is no
               reset.
        zero_lead_in: Whether all aggregate values before the first reset
                      timestamp are set to zero or not. If set True all
                      aggregate values before the first reset timestamp are
                      effectively set to zero. If False the aggregate values
                      are treated as normal and added to the cumulative value
                      until a reset occurs. zero_lead_in has no effect if there
                      are no reset timestamps withing the aggregate timespan.
                      Optional boolean. Default is False.
        """

        # initialise lists to hold the vectors that will make up our result
        start_vec = list()
        stop_vec = list()
        data_vec = list()

        # we only know how to handle the cumulative aggregate type, if we have
        # anything else raise an UnknownAggregation exception
        if aggregate_type != 'cumulative':
            # we don't know this aggregation type so raise an
            # UnknownAggregation exception
            raise weewx.UnknownAggregation
        else:
            # we've been asked for the cumulative aggregation type

            # first, capture various options that may have been passed in

            # Are we using a zero lead in? The default is to not use a zero
            # lead in.
            zero_lead_in = weeutil.weeutil.to_bool(option_dict.get('zero_lead_in',
                                                                   False))
            # Now look at the reset option (if it exists) and obtain a list
            # of timestamps, in our timespan of interest, where we will need to
            # reset the cumulative value. Also, obtain the most recent
            # timestamp before our start timestamp where there would have been
            # a reset. If no reset option was set both will be None.
            reset_list, pre_reset_ts = self.parse_reset(option_dict.get('reset'),
                                                        timespan)
            # initialise our running total
            start_total_vt = self.seed_total(obs_type, pre_reset_ts,
                                             zero_lead_in, timespan.start, db_manager)
            total = start_total_vt.value if start_total_vt.value is not None else 0.0
            unit = start_total_vt.unit
            unit_group = start_total_vt.group
            # initialise our reset timestamp index
            reset_index = 0
            # iterate over the aggregate interval timespans in the overall
            # timespan of interest
            for span in weeutil.weeutil.intervalgen(timespan.start,
                                                    timespan.stop,
                                                    aggregate_interval):
                # First up check whether we need to include this interval or
                # not. We do not include future intervals (ie intervals aftr
                # the last timestamp in the database) in our result.
                if span.start >= db_manager.last_timestamp:
                    continue
                # Get the aggregate as a ValueTuple. We are interested in the
                # sum aggregate, we will do the cumulative part of the xtype
                # later
                agg_vt = weewx.xtypes.get_aggregate(obs_type,
                                                    span,
                                                    'sum',
                                                    db_manager)
                # A WeeWX 'sum' aggregate should never return None, but just in
                # case filter out the None value lest it cause problems. By
                # definition None contributes zero to the cumulative total.
                if agg_vt.value is None:
                    # the sum for the interval concerned is None so it must
                    # contribute nothing to the cumulative value. Set the
                    # aggregate value to zero. Note that as the ValueTuple has
                    # no setter functions for its custom properties the only
                    # way to 'set' a ValueTuple custom property is to create a
                    # new ValueTuple using the appropriate existing/new values.
                    agg_vt = weewx.units.ValueTuple(0, agg_vt.unit, agg_vt.group)
                # check for unit group consistency
                if unit:
                    # we've seen a unit and unit group before but is this unit
                    # and unit group the same ? (it's OK if the unit is unknown,
                    # ie ==None)
                    if agg_vt.unit is not None and (unit != agg_vt.unit or unit_group != agg_vt.group):
                        # the unit group has changed, we cannot handle this so
                        # raise an exception
                        raise weewx.UnsupportedFeature("Cannot change unit groups "
                                                       "within an aggregation.")
                else:
                    # we haven't seen a unit and group yet so set them
                    unit, unit_group = agg_vt.unit, agg_vt.group
                # do we need to reset the running total?
                if reset_list is not None and len(reset_list) > reset_index:
                    # perhaps, but it depends...
                    if span.stop == reset_list[reset_index]:
                        # Our stop timestamp falls on the current reset
                        # timestamp so reset the running total. This means we
                        # effectively discard the current aggregate value.
                        total = 0.0
                        # since we encountered a reset timestamp increment the
                        # reset index
                        reset_index += 1
                    elif span.stop > reset_list[reset_index]:
                        # Our stop timestamp is after the current reset
                        # timestamp, so reset the running total to the current
                        # aggregate value.
                        total = agg_vt.value if agg_vt.value is not None else 0.0
                        # since we encountered a reset timestamp increment the
                        # reset index
                        reset_index += 1
                    elif agg_vt.value is not None:
                        # we haven't encountered a reset time. So we can just
                        # add the current aggregate to the running total,
                        # unless zero_lead_in is True in which case we ignore
                        # the current aggregate
                        total += agg_vt.value if not zero_lead_in else 0.0
                else:
                    # we have no reset timestamps, so just add the current
                    # aggregate to the running total
                    total += agg_vt.value if agg_vt.value is not None else 0.0
                # append the start and stop timestamps of the current span to
                # our vectors
                start_vec.append(span.start)
                stop_vec.append(span.stop)
                # append the total to our data vector
                data_vec.append(total)
        # convert our result vectors to ValueTuples and return the ValueTuples
        # as a tuple
        return (weewx.units.ValueTuple(start_vec, 'unix_epoch', 'group_time'),
                weewx.units.ValueTuple(stop_vec, 'unix_epoch', 'group_time'),
                weewx.units.ValueTuple(data_vec, unit, unit_group))

    def parse_reset(self, reset_opt, timespan):
        """Parse a reset option setting.

        Parse a reset option setting and given a timespan of interest return:
        -   a list of timestamps that fall within the timespan concerned and
            match the reset option setting
        -   the greatest matching reset timestamp (if it exists) before the
            timespan concerned
        . Also returns the last
        timestamp that falls on an aggregate period boundary before the last
        matching reset timestamp (if it exists) before the timespan.

        We could have a reset option in any of the following formats:
        -   HH:MM - reset occurs at HH:MM daily
        -   ddTHH:MM - reset occurs at HH:MM on the dd day of each month
        -   mm-ddTHH:MM - reset occurs ate HH:MM on dd-mm of each year
        -   YYYY-mm-ddTHH:MM - reset occurs at HH:MM on YYYY-mm-dd

        We could also have a keyword representing a reset time:
        -   midnight - reset occurs at 00:00 daily
        -   midday - reset occurs at 12:00 daily
        -   day - reset occurs at 00:00 daily
        -   month - reset occurs at 00:00 on the 1st of each month
        -   year - reset occurs at 00:00 on the 1st of January

        Defaults and handling of invalid formats:
        -   if an invalid time or time format is specified midnight is used as
            the time component of the reset option
        -   if an invalid date format is used (eg, 21 December 2021) the date
            component of the reset option is ignored
        -   if an invalid date is specified  (eg, 42 or 31 April) then reset
            occurs at midnight at the end of the month concerned
        """

        # initialise a variable to hold the latest reset timestamp before the
        # timespan of concern
        pre_reset_ts = None
        # do we have a rest option
        if reset_opt is None:
            # we have no reset option setting so simply return None and None
            return None, pre_reset_ts
        else:
            # do we have a reset option setting
            # first check if we have one of the recognised synonyms
            if reset_opt.lower() in XCumulative.reset_defs.keys():
                # we have a recognised synonym, so substitute in the equivalent
                # formatted reset option value
                reset_option = XCumulative.reset_defs[reset_opt.lower()]
            else:
                # we don't have a recognised synonym, so use the reset option
                # as is
                reset_option = reset_opt.lower()
            # first split on 'T'
            _split_list = reset_option.split('T')
            if len(_split_list) == 1:
                # There was no 'T', so assume we have a time in the
                # format HH:MM. Check for a valid time by attempting to parse
                # the time using strptime. We will get a ValueError if the time
                # is invalid.
                try:
                    # attempt to parse the time, we are not interested in the
                    # result so much as whether an exception occurs
                    _dt = datetime.datetime.strptime(_split_list[0], '%H:%M')
                except ValueError:
                    # could not convert specified time, so log it and default
                    # to 00:00
                    if weewx.debug >= 2:
                        log.debug("Cannot parse reset option '%s', using '00:00' daily",
                                  reset_option)
                    # the time is in the first list element
                    _split_list[0] = '00:00'
                # create a dict to hold the date and time components of the
                # reset option, we will use this later to create a list of
                # matching timestamp
                dt_params = dict()
                # obtain the hour and minute components, first split on ':'
                _split_time_list = _split_list[0].split(':')
                # obtain and add the hour and minute components to our dict
                dt_params['hour'] = int(_split_time_list[0])
                dt_params['minute'] = int(_split_time_list[1])
                dt_params['second'] = 0
                dt_params['microsecond'] = 0
                # obtain the list of reset timestamps for the timespan of
                # interest
                reset_list = self.get_ts_list(timespan, **dt_params)
                # Determine the greatest matching reset timestamp (if it
                # exists) before the timespan concerned. In this case it must
                # be within the 24-hour period immediately before the timespan
                # of interest. First, get a datetime object for the start time
                # of the timespan of interest, this will be used for our first
                # 'guess'.
                _dt_timespan_start = datetime.datetime.fromtimestamp(timespan.start)
                # calculate our first 'guess'
                _pre_reset_dt = _dt_timespan_start.replace(**dt_params)
                # the timestamp must be before our timespan of interest
                if int(time.mktime(_pre_reset_dt.timetuple())) > timespan.start:
                    # our first guess is after the start of the timespan, so
                    # the timestamp we want must be from the day before
                    _pre_reset_dt = _pre_reset_dt - datetime.timedelta(days=1)
                # finally, convert the datetime object to a timestamp
                pre_reset_ts = int(time.mktime(_pre_reset_dt.timetuple()))
            elif len(_split_list) == 2:
                # we have a 'T', so we need to look for both date and time
                # components
                # create a dict to hold the date and time components of the
                # reset option, these parameters will be applied against a
                # datetime object later to obtain our reset timestamps
                dt_params = dict()
                # First look at the time. Check for a valid time by attempting
                # to parse the time using strptime. We will get a ValueError if
                # the time is invalid.
                try:
                    # attempt to parse the time, we are not interested in the
                    # result so much as whether an exception occurs
                    _dt = datetime.datetime.strptime(_split_list[1], '%H:%M')
                except ValueError:
                    # could not convert the specified time so log it and
                    # default to 00:00
                    if weewx.debug >= 2:
                        log.debug("Cannot parse time in reset option '%s', using '00:00'",
                                  reset_option)
                    # on this occasion the time is in the second list element
                    _split_list[1] = '00:00'
                # we now have a valid time, so split on ':' to obtain the hour
                # and minute components
                _split_time_list = _split_list[1].split(':')
                # obtain and add the hour and minute components to our dict
                dt_params['hour'] = int(_split_time_list[0])
                dt_params['minute'] = int(_split_time_list[1])
                dt_params['second'] = 0
                dt_params['microsecond'] = 0
                # Now look at the date. We only accept a limited number of date
                # formats so iterate over the acceptable date formats looking
                # for a match
                for date_fmt in ('%d', '%m-%d', '%Y-%m-%d'):
                    # Check for a valid date by attempting to parse the date
                    # using strptime. We will get a ValueError if the date is
                    # invalid.
                    try:
                        _date_dt = datetime.datetime.strptime(_split_list[0], date_fmt)
                    except ValueError:
                        # we could not parse the date string using the current
                        # format, so pass and try the next format
                        pass
                    else:
                        # we have a valid date component
                        # there must be a day of month value so add it to our
                        # dict of date-time parameters
                        dt_params['day'] = _date_dt.timetuple().tm_mday
                        # if we have a month add it to our dict of date-time
                        # parameters
                        if '%m' in date_fmt:
                            dt_params['month'] = _date_dt.timetuple().tm_mon
                        # if we have a year add it to our dict of date-time
                        # parameters
                        if '%Y' in date_fmt:
                            dt_params['year'] = _date_dt.timetuple().tm_year
                        # since we have a match we can exit the for loop
                        continue
                # even though we have finished parsing the date-time reset
                # option, check if we had a valid date string, we could have
                # arrived here having found no date format match
                if 'day' not in dt_params:
                    # we could not parse the date string, log it and
                    # return None, None
                    if weewx.debug >= 2:
                        log.debug("Cannot parse date in reset option '%s'",
                                  reset_option)
                    return None, pre_reset_ts
                # we have a valid date reset option so now we can produce the
                # reset timestamp list
                reset_list = self.get_ts_list(timespan, **dt_params)
                # now determine the pre_reset_ts
                # obtain the timespan start as a datetime object
                _dt_start = datetime.datetime.fromtimestamp(timespan.start)
                # now apply the reset params
                _dt = _dt_start.replace(**dt_params)
                # and convert to a timestamp
                _dt_ts = int(time.mktime(_dt.timetuple()))
                if 'year' in dt_params:
                    # A year, month and day of month was specified. This nails
                    # a date so we are only interested if the resulting
                    # timestamp is before our timespan start
                    pre_reset_ts = _dt_ts if _dt_ts < timespan.start else None
                elif 'month' in dt_params:
                    # A month and day of month was specified. This could be
                    # from the year of our timespan start or it could be from
                    # the year before.
                    if _dt_ts < timespan.start:
                        # it's from the current year
                        pre_reset_ts = _dt_ts
                    else:
                        # It's from the year before, so get a datetime object
                        # for the year before. We need to be careful as
                        # February 29 could be a problem! Wrap in a try..except
                        # and deal with any exceptions raised.
                        try:
                            _dt_last_year = _dt.replace(year=_dt.year - 1)
                        except ValueError:
                            # we amost certainly have February 29, go back one
                            # year and one day
                            _dt_last_year = _dt.replace(year=_dt.year - 1, day=_dt.day - 1)
                        # extract a timestamp from the resulting datetime
                        # object
                        pre_reset_ts = int(time.mktime(_dt_last_year.timetuple()))
                elif 'day' in dt_params:
                    # A day of month was specified. This could be from the
                    # month of our timespan start or it could be from the month
                    # before.
                    if _dt_ts < timespan.start:
                        # it's from the current month
                        pre_reset_ts = _dt_ts
                    else:
                        # It's from the month before, so get a datetime object
                        # for the month before. We need to be careful in case
                        # we are in January or in case the previous month does
                        # not have enough days.
                        if _dt.month == 1:
                            # we are in January, so we need to go back one year
                            # and move to December
                            _dt_last_month = _dt.replace(year=_dt.year - 1, month=12)
                        else:
                            # we can just subtract one month, but we also need
                            # to enure we have enough days in the previous
                            # month. We will handle this by subtracting one
                            # month and if we have an invalid date subtract a
                            # day, if still invalid subtract another day. Keep
                            # going until we have a valid date but don't
                            # subtract more than three days (worst case
                            # 31 March -28 February)
                            err = None
                            for offset in range(4):
                                try:
                                    _dt_last_month = _dt.replace(month=_dt.month - 1, day=_dt.day - offset)
                                except ValueError as e:
                                    # we have an invalid month/day combination,
                                    # keep the error for later
                                    err = e
                                    # move onto the next day
                                    continue
                                else:
                                    # we have a valid month/day combination,
                                    # break out of the loop and continue
                                    break
                            else:
                                # If we made it here the loop exhausted all
                                # values but did not find a valid month/day
                                # combination. This should never happen, but if
                                # it does raise a ValueError from the last
                                # ValueError we saw.
                                if err:
                                    raise ValueError() from err
                        # we now have a datetime object, extract a timestamp
                        # from the object
                        pre_reset_ts = int(time.mktime(_dt_last_month.timetuple()))
                else:
                    # We should never arrive here; we have a valid date but no
                    # year, month or day of month. But if for some reason we do
                    # log it and return None, None.
                    if weewx.debug >= 2:
                        log.debug("Cannot parse date in reset option '%s'",
                                  reset_option)
                    return None, pre_reset_ts
            else:
                # we have a reset option we cannot parse
                _msg = "Cannot parse reset option '%s'"
                raise weewx.ViolatedPrecondition(_msg)
            # if we made it here we have a reset list and a pre-timespan reset
            # timestamp, return them
            return reset_list, pre_reset_ts

    @staticmethod
    def get_ts_list(timespan, **dt_params):
        """Obtain a list of matching timestamps.

        Given a timespan and a dictionary of date-time parameters obtain a list
        of timestamps within the timespan that match the date-time parameters.
        If no matching timestamps are found return an empty list.
        """

        # initialise an empty list for the result
        ts_list = list()
        # iterate over each day in the timespan of concern
        for day_span in weeutil.weeutil.genDaySpans(timespan.start, timespan.stop):
            # obtain a datetime object based on the timestamp for the start of
            # day
            _dt = datetime.datetime.fromtimestamp(day_span.start)
            # Using the start of day datetime object update that object with
            # the date-time parameters for matching date-times. The resulting
            # date time object may fall within or without the current day.
            _day_reset_dt = _dt.replace(**dt_params)
            # convert the modified datetime object to a timestamp
            _day_reset_ts = time.mktime(_day_reset_dt.timetuple())
            # we are only interested in the resulting timestamp if it falls
            # somewhere within the timespan of interest
            if timespan.start <= _day_reset_ts < timespan.stop:
                # the timestamp does fall within the timespan of interest, so
                # add it to the list of matching timestamps
                ts_list.append(_day_reset_ts)
        # return the list of matching timestamps
        return ts_list

    @staticmethod
    def seed_total(obs_type, pre_reset_ts, zero_lead_in, start_ts, db_manager):
        """Determine the starting value for the running sum.

        The cumulative total must be initialised before the cumulative series
        is calculated. This 'seed' value is the sum of the field concerned over
        the period from the previous reset timestamp through to the start of
        the timespan of concern. If zero_lead_in is set True the 'seed' value
        is zero. If zero_lead_in is set False a simple aggregate is calculated.
        """

        if pre_reset_ts is None or zero_lead_in:
            # We don't have a pre-timespan reset ts or we have been directed to
            # start at zero. Either way the start value will be zero.
            start_vt = weewx.units.ValueTuple(0.0, None, None)
        else:
            # We have a pre-timespan reset ts and need to calculate the start
            # value from the archive. We don't need anything fancy, we can just
            # do a straight out sum query on the archive field concerned from
            # the pre-timespan reset ts to the timespan start ts.
            # determine the timespan of interest, it starts with the rest ts
            # and ends with the start of the timespan of the cumulative aggregate
            timespan = weeutil.weeutil.TimeSpan(pre_reset_ts, start_ts)
            # obtain the sum as a ValueTuple
            start_vt = weewx.xtypes.get_aggregate(obs_type, timespan, 'sum', db_manager)
        return start_vt


# ==============================================================================
#                           Class StdCumulativeXType
# ==============================================================================

class StdCumulativeXType(weewx.engine.StdService):
    """Instantiate and register the XCumulative XType."""

    def __init__(self, engine, config_dict):
        super(StdCumulativeXType, self).__init__(engine, config_dict)

        # highlight our version in the log, our loading will be included in the
        # log when debug=1, so log our version at the debug log level
        log.debug("StdCumulativeXType v%s", XCUMULATIVE_VERSION)
        # obtain an XCumulative XType object
        self.xcumulative = XCumulative()
        # Add the XCumulative XType object to the front of the WeeWX XType
        # list. This is necessary so that the XCumulative XType is chosen in
        # preference to any other XTypes when a cumulative series aggregate is
        # being sought.
        weewx.xtypes.xtypes.insert(0, self.xcumulative)

    def shutDown(self):

        # remove the XCumulative XType from the list of XTypes
        weewx.xtypes.xtypes.remove(self.xcumulative)
