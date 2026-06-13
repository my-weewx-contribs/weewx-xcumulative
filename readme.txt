Cumulative XType Extension

Description

The 'Cumulative XType' extension is a WeeWX extension that installs an XType 
that provides cumulative series data with a flexible, user settable reset 
date-time. When used with the WeeWX image generator this enables the generation 
of cumulative plots that reset at a specified time or date and time. 
For example, a cumulative rain plot can be produced with the rainfall total 
resetting to zero at midnight.

The extension consists of a single WeeWX XType and an associated WeeWX service. 
A number of config options can be used to control the operation of the 
'Cumulative XType'.


Pre-requisites

The 'Cumulative XType' extension requires WeeWX v4.6.0 or greater and Python 3.


Installation instructions

To install the 'Cumulative XType' extension:
  
1.  Install the extension package:

    weectl extension install https://github.com/my-weewx-contribs/weewx-xcumulative/releases/latest/download/xcumulative.zip

    Note: For non-package WeeWX installs (ie 'pip' or 'git' installs) you may
    need to activate the relevant virtual environment and call the above
    command using the relevant python interpreter and applicable paths. Refer
    to the applicable WeeWX install instructions
    (https://weewx.com/docs/5.3/#installation) for examples.

2.  Restart the WeeWX daemon:
    
    sudo systemctl restart weewx
        
    or

    sudo /etc/init.d/weewx restart

    or

    sudo service weewx restart

3.  You may now use the aggregate type 'cumulative' in WeeWX report templates
and plot definitions to produce cumulative series data/plots with user
selectable reset times.


Configuration options

The following configuration options may be used to control the operation of the
'Cumulative XType' extension:

-   'reset'. An optional string that specifies the date-time at which the
cumulative series will be reset to zero. Format is '[[mm-][dd]T]HH:MM' where:
  
    mm is the month number (1..12)
    dd is the day of the month (1..31)
    T is the string literal T
    HH is the hour of the day (0..23)
    MM is the minute of the hour (00..59)

    For example:

        reset = 12:30
        
    would produce series data or a plot where the cumulative value would reset
    at 12:30 daily
        
        reset = 12T00:00
        
    would produce series data or a plot where the cumulative value would reset
    at midnight (00:00) on the 12th day of each month
        
        reset = 06-12T02:00
        
    would produce series data or a plot where the cumulative value would reset
    at 2am (02:00) on the 12th of June each year

    In addition, 'reset' also accepts the following shorthand values:

    -   'midnight'. Midnight each day, equivalent to 00:00.
    -   'midday'. Midday each day, equivalent to 12:00.
    -   'day'. Midnight each day, equivalent to 00:00.
    -   'month'. Midnight on the first of each month, equivalent to 01T00:00.
    -   'year'. Midnight on the first of January each year, equivalent to
                01-01T00:00.

    The default is no reset.

-   'zero_lead_in'. An optional string that specifies whether to start the
cumulative series from zero or the cumulative value had the 'reset' config
option been applied before the time span of concern. If 'zero_lead_in' is set
'True' the cumulative value starts from zero. If 'zero_lead_in' is omitted or
set 'False' starts from the cumulative value had the 'reset' config option been
applied before the time span of concern. This is useful when plotting
cumulative data. Refer to the Note below for a more detailed explanation.

    The default is 'False'

    Note: The cumulative value starting at zero may be acceptable in some
    cases, however, in other cases, such as some plots, it may produce
    misleading or incorrect output. Consider a day plot of cumulative rainfall
    that resets at midnight. If there has been rainfall over the past two days
    the plot concerned will show the correct cumulative total for portion of
    the plot showing the current day, but the portion of the plot for the
    previous day will be incorrect if there was rainfall in the portion of the
    previous day that is not included in the plot. This may be corrected by
    setting 'zero_lead_in' to 'False' which will cause the cumulative value to
    start at the cumulative value calculated from the previous date-time
    specified by the 'reset' config option through until the start of the
    timespan of interest.


Example usage

The following examples show how the 'Cumulative XType' may be used.

Templates

The following example template tags show how the 'Cumulative XType' may be used
to generate cumulative series data in WeeWX report templates:

-   To produce a series showing the cumulative rainfall for the current day
    using five-minute intervals and resetting the cumulative value at 9am:

        $day.rain.series(aggregate_type=cumulative, aggregate_interval=300, reset='09:00')

-   To produce a JSON format series showing the cumulative rainfall for the
    current day using five-minute intervals and resetting the cumulative value
    at 9am:

        $day.rain.series(aggregate_type=cumulative, aggregate_interval=300,
                         reset='09:00').json

-   To produce a JSON format series showing the cumulative rainfall for the
    current month using one-hour intervals, starting at zero and resetting the
    cumulative value at midnight on each day:

        $month.rain.series(aggregate_type=cumulative, aggregate_interval=3600,
                           reset='midnight', zero_lead_in='true').json

-   To produce a JSON format series showing the cumulative rainfall for the
    current month using one-hour intervals and no reset:

        $month.rain.series(aggregate_type=cumulative, aggregate_interval=3600).json


Plots

The following example skin config file plot definition extracts show how the
'Cumulative XType' may be used to generate cumulative plots:

-   To produce a day plot showing cumulative rainfall that resets at 9am each
    day:

        [ImageGenerator]
            ....
            [[day_images]]
                ....
                [[[dayrain]]]
                    [[[[rain]]]]
                        label = Day Rainfall
                        aggregate_type = cumulative
                        aggregate_interval = 300
                        # reset at 9am
                        reset = 09:00

-   To produce a day plot showing cumulative rainfall with no reset:

        [ImageGenerator]
            ....
            [[day_images]]
                ....
                [[[dayrain]]]
                    [[[[rain]]]]
                        label = Day Rainfall
                        aggregate_type = cumulative
                        aggregate_interval = 300

-   To produce a day plot showing cumulative rainfall that starts at zero and
    resets at 9am each day:

        [ImageGenerator]
            ....
            [[day_images]]
                ....
                [[[dayrain]]]
                    [[[[rain]]]]
                        label = Day Rainfall
                        aggregate_type = cumulative
                        aggregate_interval = 300
                        # reset at 9am
                        reset = 09:00
                        zero_lead_in = true
  
-   To produce a week plot showing daily cumulative rainfall (ie resets at
    midnight each day):

        [ImageGenerator]
            ....
            [[week_images]]
                ....
                [[[weekrain]]]
                    [[[[rain]]]]
                        label = Daily Rainfall
                        aggregate_type = cumulative
                        aggregate_interval = 300
                        # reset at midnight
                        reset = midnight

-   To produce a year plot showing monthly cumulative rainfall (ie resets at
    midnight on the first of each month):

        [ImageGenerator]
            ....
            [[year_images]]
                ....
                [[[yearrain]]]
                    [[[[rain]]]]
                        label = Monthly Rainfall
                        aggregate_type = cumulative
                        aggregate_interval = 86400 # 1 day
                        # reset at midnight on the first of each month
                        reset = 01T00:00
