# Copyright (c) 2016 Noviflow
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

class AttrDict(dict):
    "An object that allows attrDict.foo or attrDict['foo']"
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.parser = None

def get_parser(files=None):
    "Read config files for SS2"
    files = files or DEFAULT_FILES

    parser = ConfigParser()
    parser.readfp(open(DEFAULT_CONFIG))
    parser.read(files)
    return parser

def read_config(files=None, section="Core"):
    "Helper to get an AttrDict of the config from the specified section"
    parser = get_parser(files)
    items = get_section(parser, section)
    config = parse_types(items, parser)
    return config

def get_section(parser, section):
    "Get resolved items from the appropriate section/subsection"
    items = []
    # Use DEFAULTS rather than DEFAULT so we don't get ConfigParser's default
    # behavior when we finally get the items in the full section path
    items += parser.items("DEFAULTS")
    path = section.split("/")
    if len(path) <= 1:
        return items + parser.items(section)

    search = []
    for p in path[:-1]:
        search.append(p)
        if parser.has_section("/".join(search)):
            items += parser.items("/".join(search))
        if parser.has_section("/".join(search + ["DEFAULTS"])):
            items += parser.items("/".join(search + ["DEFAULTS"]))

    items += parser.items(section)
    return items

def get_subsections(parser, section, deep=False):
    "Get a list of subsections for the specified section"
    sections = []
    section_depth = len(section.split("/"))
    for s in parser.sections():
        if not deep:
            depth = len(s.split("/"))
            if depth > section_depth + 1:
                continue
        if not s.startswith(section + "/"):
            continue
        if s.endswith("/DEFAULTS"):
            continue
        sections.append(s)

    return sections

def parse_types(items, parser=None):
    "Parse items list in to an AttrDict with automatic type conversion"
    config = AttrDict()
    config.parser = parser

    for k, v in items:
        try:
            if "." in v:
                v = float(v)
            elif v in ["true", "yes", "on"]:
                v = True
            elif v in ["false", "no", "off"]:
                v = False
            else:
                v = int(v, 0)
        except ValueError:
            pass

        if "." in k:
            # Allow dictionary paths in config. For example:
            #   foo.bar: baz
            # Can be accessed as `config.foo.bar`
            path = k.split(".")
            current = config
            for p in path[:-1]:
                # If needed, reset current path to an empty AttrDict
                if p in current and isinstance(current[p], AttrDict):
                    current = current[p]
                else:
                    current[p] = AttrDict()
                    current = current[p]
                    config.parser = parser

            current[path[-1]] = v
        else:
            config[k] = v

    return config
