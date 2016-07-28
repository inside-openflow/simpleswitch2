# Copyright (c) 2016 Inside OpenFlow
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy,
# modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""
SimpleSwitch 2.0 (SS2) Configuration Loader

Will first load `defaults.cfg` relative in the `ss2` package, then load
`ss2.cfg` in the current working directory by default.
"""

import os
try:
    from ConfigParser import ConfigParser
except ImportError:
    from configparser import ConfigParser

DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), 'defaults.cfg')
DEFAULT_FILES = ['ss2.cfg']

def read_config(files=None, section="Core"):
    "Read config files for SS2"
    files = files or DEFAULT_FILES

    parser = ConfigParser()
    parser.readfp(open(DEFAULT_CONFIG))
    parser.read(files)

    class AttrDict(dict):
        "An object that allows attrDict.foo or attrDict['foo']"
        __getattr__ = dict.__getitem__
        __setattr__ = dict.__setitem__
        __delattr__ = dict.__delitem__

    config = AttrDict()
    for k, v in parser.items(section):
        try:
            if "." in v:
                v = float(v)
            else:
                v = int(v, 0)
        except ValueError:
            pass

        config[k] = v

    return config
