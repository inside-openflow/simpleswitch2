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
SimpleSwitch 2.0 (SS2) ACL Controller Application

TODO: Diagram the table structure used here
"""

from . import config, util
from .app import SS2App
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ethernet, ether_types as ether, packet
from ryu.ofproto import ofproto_v1_3


class SS2ACL(app_manager.RyuApp, SS2App):
    "SS2 ACL RyuApp"
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SS2ACL, self).__init__(*args, **kwargs)
        self.configParser = config.get_parser()
        self.config = config.read_config("ACL")


    ## Event Handlers

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        "Handle new datapaths attaching to Ryu"
        dp = ev.msg.datapath

        self.send_msgs(dp, self.add_datapath(dp))

    ## Instance Helper Methods

    def add_datapath(self, dp):
        "Add the specified datapath to our app by adding default rules"

        msgs = self.clean_all_flows(dp)
        msgs += self.add_default_flows(dp)
        return msgs

    def add_default_flows(self, dp):
        "Add ACL rules from configuration"
        rules = self.get_ACL_rules()
        msgs = []
        for rule in rules:
            msgs += self.get_flows_for_rule(dp, rule)

        return msgs

    def get_ACL_rules(self):
        "Returns a list of ACLRule instances from the config file"

class ACLRule(object):
    def __init__(self, **data):
        self.data = data

    def to_flows(self, dp):
        "Return a list of flowmod data dicts for this rule"
