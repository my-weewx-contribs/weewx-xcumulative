"""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

                 Installer for the Cumulative XType Extension

Version: 0.3.0                                          Date: ?? June 2026

Revision History
    ?? June 2026        v0.3.0
        - now uses 'distutils' free version comparison
    25 October 2022     v0.2.0
        - no change, version change only
    23 October 2022     v0.1.0
        - initial implementation
"""

# python imports
from setup import ExtensionInstaller

# WeeWX imports
import weewx


REQUIRED_WEEWX_VERSION = "4.6.0"
XCUMULATIVE_VERSION = "0.3.0"


def version_compare(v1, v2):
    """Basic 'distutils' and 'packaging' free version comparison.

    v1 and v2 are WeeWX version numbers in string format.

    Returns:
        0 if v1 and v2 are the same
        -1 if v1 is less than v2
        +1 if v1 is greater than v2
    """

    import itertools
    mash = itertools.zip_longest(v1.split('.'), v2.split('.'), fillvalue='0')
    for x1, x2 in mash:
        try:
            y1, y2 = int(x1), int(x2)
        except ValueError:
            y1, y2 = x1, x2
        if y1 > y2:
            return 1
        if y1 < y2:
            return -1
    return 0


def loader():
    return XCumulativeInstaller()


class XCumulativeInstaller(ExtensionInstaller):
    def __init__(self):
        if version_compare(weewx.__version__, REQUIRED_WEEWX_VERSION) < 0:
            msg = "%s requires WeeWX %s or greater, found %s" % (''.join(('Cumulative XType ', XCUMULATIVE_VERSION)),
                                                                 REQUIRED_WEEWX_VERSION,
                                                                 weewx.__version__)
            raise weewx.UnsupportedFeature(msg)
        super(XCumulativeInstaller, self).__init__(
            version=XCUMULATIVE_VERSION,
            name='XCumulative',
            description='A WeeWX XType to produce cumulative series data with user specified reset times.',
            author="R",
            author_email="mrsnootle<@>gmail.com",
            xtype_services=['user.xcumulative.StdCumulativeXType'],
            files=[('bin/user', ['bin/user/xcumulative.py'])]
        )
