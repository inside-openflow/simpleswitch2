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
SimpleSwitch 2.0 (SS2) Core Controller Application

TODO: Diagram the table structure used here
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ethernet, ether_types, packet
from ryu.ofproto import ofproto_v1_3

SS2_COOKIE = 0x42C00C13     # A 64-bit cookie to mark our flow entries
TABLE_ACL = 0
TABLE_ETH_SRC = 1
TABLE_ETH_DST = 2
LEARN_TIMEOUT = 60

class SS2Core(app_manager.RyuApp):
    "SS2 RyuApp"
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SS2Core, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        "Handle new datapaths attaching to Ryu"
        msgs = []
        msgs.extend(self.add_datapath(ev.msg.datapath))

        self.send_msgs(msgs)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        "Handle incoming packets from a datapath"
        dp = ev.msg.datapath
        in_port = ev.msg.match['in_port']

        # Parse the packet
        pkt = packet.Packet(ev.msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        msgs = []
        msgs.extend(self.learn_source(
            dp=dp,
            in_port=in_port,
            eth_src=eth.src))

        self.send_msgs(msgs)

    def add_datapath(self, dp):
        "Add the specified datapath to our app by adding default rules"
        msgs = []
        msgs.extend(self.clean_all_flows(dp))
        msgs.extend(self.add_default_flows(dp))
        return msgs

    def learn_source(self, dp, in_port, eth_src):
        msgs = []
        msgs.extend(self.unlearn_source(dp, eth_src=eth_src))
        msgs.extend(self.add_eth_src_flow(dp, in_port, eth_src))
        return msgs

    def unlearn_source(self, dp, eth_src):
        "remove any existing flow entries for this MAC address"
        msgs = []
        return msgs
