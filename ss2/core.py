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
SimpleSwitch 2.0 (SS2) Core Controller Application

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

class SS2Core(app_manager.RyuApp, SS2App):
    "SS2 RyuApp"
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SS2Core, self).__init__(*args, **kwargs)
        self.config = config.read_config()
        self.host_cache = util.HostCache(self.config.host_cache_timeout)


    ## Event Handlers

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        "Handle new datapaths attaching to Ryu"

        msgs = self.add_datapath(ev.msg.datapath)

        self.send_msgs(ev.msg.datapath, msgs)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        "Handle incoming packets from a datapath"

        dp = ev.msg.datapath
        in_port = ev.msg.match['in_port']

        # Parse the packet
        pkt = packet.Packet(ev.msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ensure this host was not recently learned to avoid flooding the switch
        # with the learning messages if the learning was already in process.
        if not self.host_cache.is_new_host(dp.id, in_port, eth.src):
            return

        msgs = self.learn_source(
            dp=dp,
            port=in_port,
            eth_src=eth.src)

        self.send_msgs(dp, msgs)

    ## Instance Helper Methods

    def add_datapath(self, dp):
        "Add the specified datapath to our app by adding default rules"

        msgs = self.clean_all_flows(dp)
        msgs += self.add_default_flows(dp)
        return msgs

    def learn_source(self, dp, port, eth_src):
        "Learn the port associated with the source MAC"

        msgs = self.unlearn_source(dp, eth_src=eth_src)
        msgs += self.add_eth_src_flow(dp, in_port=port, eth_src=eth_src)
        msgs += self.add_eth_dst_flow(dp, out_port=port, eth_dst=eth_src)
        return msgs

    def unlearn_source(self, dp, eth_src):
        "Remove any existing flow entries for this MAC address"

        msgs = [self.flowdel(dp, self.config.table_eth_src,
                             match=self.match(dp, eth_src=eth_src))]
        msgs += [self.flowdel(dp, self.config.table_eth_dst,
                              match=self.match(dp, eth_dst=eth_src))]
        msgs += [self.barrier_request(dp)]
        return msgs

    def add_default_flows(self, dp):
        "Add the default flows needed for this environment"

        ofp = dp.ofproto

        msgs = []
        ## TABLE_ACL
        # Add a low priority table-miss flow to forward to the switch table.
        # Other modules can add higher priority flows as needed.
        instructions = [self.goto_table(dp, self.config.table_l2_switch)]
        msgs += [self.flowmod(dp, self.config.table_acl,
                              match=self.match(dp),
                              priority=self.config.priority_low,
                              instructions=instructions)]

        ## TABLE_L2_SWITCH
        # Drop certain packets that should not be broadcast or processed
        # (Mimic Faucet)

        def _drop(match):
            "Helper to create a drop flow entry for table_l2_switch"
            return [self.flowmod(dp, self.config.table_l2_switch,
                                 match=match, priority=self.config.priority_max,
                                 instructions=[])]

        # Drop LLDP
        msgs += _drop(self.match(dp, eth_type=ether.ETH_TYPE_LLDP))

        # Drop STDP BPDU
        msgs += _drop(self.match(dp, eth_dst='01:80:c2:00:00:00'))
        msgs += _drop(self.match(dp, eth_dst='01:00:0c:cc:cc:cd'))

        # Drop Broadcast Sources
        msgs += _drop(self.match(dp, eth_src='ff:ff:ff:ff:ff:ff'))

        # All other packets go to table TABLE_ETH_SRC
        match = self.match(dp)
        instructions = [self.goto_table(dp, self.config.table_eth_src)]
        msgs += [self.flowmod(dp, self.config.table_l2_switch,
                              match=match,
                              priority=self.config.priority_min,
                              instructions=instructions)]

        ## TABLE_ETH_SRC
        # Table-miss sends to controller and sends to TABLE_ETH_DST
        # We send to TABLE_ETH_DST because the SRC rules will hard timeout
        # before the DST rules idle timeout. This gives a last chance to
        # prevent a flood event while the controller relearns the address.
        actions = [self.action_output(dp, ofp.OFPP_CONTROLLER, max_len=256)]
        instructions = [self.apply_actions(dp, actions),
                        self.goto_table(dp, self.config.table_eth_dst)]
        msgs += [self.flowmod(dp, self.config.table_eth_src,
                              match=match,
                              priority=self.config.priority_min,
                              instructions=instructions)]

        ## TABLE_ETH_DST
        # Flood multicast (Mimic Faucet)
        flood_addrs = [
            ('01:80:c2:00:00:00', '01:80:c2:00:00:00'), # 802.x
            ('01:00:5e:00:00:00', 'ff:ff:ff:00:00:00'), # IPv4 multicast
            ('33:33:00:00:00:00', 'ff:ff:00:00:00:00'), # IPv6 multicast
            ('ff:ff:ff:ff:ff:ff', None) # Ethernet broadcast
        ]
        actions = [self.action_output(dp, ofp.OFPP_FLOOD)]
        instructions = [self.apply_actions(dp, actions)]
        for eth_dst in flood_addrs:
            match = self.match(dp, eth_dst=eth_dst)
            msgs += [self.flowmod(dp, self.config.table_eth_dst,
                                  match=match,
                                  priority=self.config.priority_max,
                                  instructions=instructions)]

        # Table-miss floods
        match = self.match(dp)
        actions = [self.action_output(dp, ofp.OFPP_FLOOD)]
        instructions = [self.apply_actions(dp, actions)]
        msgs += [self.flowmod(dp, self.config.table_eth_dst,
                              match=match,
                              priority=self.config.priority_min,
                              instructions=instructions)]
        return msgs

    def add_eth_src_flow(self, dp, in_port, eth_src):
        "Add flow to mark the source learned at a specific port"

        match = self.match(dp, eth_src=eth_src, in_port=in_port)
        instructions = [self.goto_table(dp, self.config.table_eth_dst)]
        return [self.flowmod(dp, self.config.table_eth_src,
                             hard_timeout=self.config.learn_timeout,
                             match=match,
                             instructions=instructions,
                             priority=self.config.priority_high)]

    def add_eth_dst_flow(self, dp, out_port, eth_dst):
        "Add flow to forward packet sent to eth_dst to out_port"

        match = self.match(dp, eth_dst=eth_dst)
        actions = [self.action_output(dp, out_port)]
        instructions = [self.apply_actions(dp, actions)]
        return [self.flowmod(dp, self.config.table_eth_dst,
                             idle_timeout=self.config.learn_timeout,
                             match=match,
                             instructions=instructions,
                             priority=self.config.priority_high)]
