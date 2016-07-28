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

import logging
import time
from . import config
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ethernet, packet
from ryu.ofproto import ofproto_v1_3

class SS2Core(app_manager.RyuApp):
    "SS2 RyuApp"
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SS2Core, self).__init__(*args, **kwargs)
        self.config = config.read_config()
        self.host_cache = HostCache(self.config.host_cache_timeout)


    ## Event Handlers

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        "Handle new datapaths attaching to Ryu"

        msgs = []
        msgs.extend(self.add_datapath(ev.msg.datapath))

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

        msgs = []
        msgs.extend(self.learn_source(
            dp=dp,
            port=in_port,
            eth_src=eth.src))

        self.send_msgs(dp, msgs)


    ## Static Helper Methods

    @staticmethod
    def send_msgs(dp, msgs):
        "Send all the messages provided to the datapath"

        for msg in msgs:
            dp.send_msg(msg)

    @staticmethod
    def apply_actions(dp, actions):
        "Generate an OFPInstructionActions message with OFPIT_APPLY_ACTIONS"

        return dp.ofproto_parser.OFPInstructionActions(
            dp.ofproto.OFPIT_APPLY_ACTIONS, actions)

    @staticmethod
    def action_output(dp, port, max_len=None):
        "Generate an OFPActionOutput message"

        kwargs = {'port': port}
        if max_len != None:
            kwargs['max_len'] = max_len

        return dp.ofproto_parser.OFPActionOutput(**kwargs)

    @staticmethod
    def goto_table(dp, table_id):
        "Generate an OFPInstructionGotoTable message"

        return dp.ofproto_parser.OFPInstructionGotoTable(table_id)

    @staticmethod
    def match(dp, in_port=None, eth_dst=None, eth_src=None, eth_type=None,
              **kwargs):
        "Generate an OFPMatch message"

        if in_port != None:
            kwargs['in_port'] = in_port
        if eth_dst != None:
            kwargs['eth_dst'] = eth_dst
        if eth_src != None:
            kwargs['eth_src'] = eth_src
        if eth_type != None:
            kwargs['eth_type'] = eth_type
        return dp.ofproto_parser.OFPMatch(**kwargs)

    @staticmethod
    def barrier_request(dp):
        """Generate an OFPBarrierRequest message

        Used to ensure all previous flowmods are applied before running the
        flowmods after this request. For example, make sure the flowmods that
        delete any old flows for a host complete before adding the new flows.
        Otherwise there is a chance that the delete operation could occur after
        the new flows are added in a multi-threaded datapath.
        """

        return dp.ofproto_parser.OFPBarrierRequest(datapath=dp)


    ## Instance Helper Methods

    def all_ss2_tables(self):
        "Returns a touple of all tables used by SS2Core"

        return (self.config.table_acl, self.config.table_eth_src,
                self.config.table_eth_dst)

    def flowmod(self, dp, table_id, command=None, idle_timeout=None,
                hard_timeout=None, priority=None, buffer_id=None,
                out_port=None, out_group=None, flags=None, match=None,
                instructions=None):
        "Generate an OFPFlowMod message with the cookie already specified"

        mod_kwargs = {
            'datapath': dp,
            'table_id': table_id,
            'command': command or dp.ofproto.OFPFC_ADD,
            'cookie': self.config.cookie
        }
        # Selectively add kwargs so ofproto defaults will be used otherwise.
        # Not using **kwargs in method defintion so arguments can be easy to
        # parse for static analysis (autocompletion)
        if idle_timeout != None:
            mod_kwargs['idle_timeout'] = idle_timeout
        if hard_timeout != None:
            mod_kwargs['hard_timeout'] = hard_timeout
        if priority != None:
            mod_kwargs['priority'] = priority
        if buffer_id != None:
            mod_kwargs['buffer_id'] = buffer_id
        if out_port != None:
            mod_kwargs['out_port'] = out_port
        if out_group != None:
            mod_kwargs['out_group'] = out_group
        if flags != None:
            mod_kwargs['flags'] = flags
        if match != None:
            mod_kwargs['match'] = match
        if instructions != None:
            mod_kwargs['instructions'] = instructions
        return dp.ofproto_parser.OFPFlowMod(**mod_kwargs)

    def flowdel(self, dp, table_id, priority=None, match=None, out_port=None):
        "Generate an OFPFlowMod through flowmod with the OFPFC_DELETE command"

        return self.flowmod(dp, table_id,
                            priority=priority,
                            match=match,
                            command=dp.ofproto.OFPFC_DELETE,
                            out_port=out_port or dp.ofproto.OFPP_ANY,
                            out_group=dp.ofproto.OFPG_ANY)

    def clean_all_flows(self, dp):
        "Remove all flows with the SS2 cookie from all tables"

        msgs = []
        for table in self.all_ss2_tables():
            msgs += [self.flowdel(dp, table)]
        return msgs

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
        # Flood multicast
        flood_addrs = [
            ('01:80:c2:00:00:00', '01:80:c2:00:00:00'), # LLDP, other 802.x
            ('01:00:5e:00:00:00', 'ff:ff:ff:00:00:00'), # IPv4 multicast
            ('33:33:00:00:00:00', 'ff:ff:00:00:00:00'), # IPv6 multicast
            ('ff:ff:ff:ff:ff:ff', None) # Ethernet broadcast
        ]
        actions = [self.action_output(dp, ofp.OFPP_FLOOD)]
        instructions = [self.apply_actions(dp, actions)]
        for eth_dst in flood_addrs:
            match = self.match(dp, eth_dst=eth_dst)
            msgs += [self.flowmod(dp, self.config.table_acl,
                                  match=match,
                                  priority=self.config.priority_low,
                                  instructions=instructions)]

        # All unicast packets go to table TABLE_ETH_SRC
        match = self.match(dp)
        instructions = [self.goto_table(dp, self.config.table_eth_src)]
        msgs += [self.flowmod(dp, self.config.table_acl,
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
        # Table-miss sends to controller and floods
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

class _HostCacheEntry(object):
    "Basic class to hold data on a cached host"

    def __init__(self, dpid, port, mac):
        self.dpid = dpid
        self.port = port
        self.mac = mac
        self.timestamp = time.time()
        self.counter = 0

class HostCache(object):
    "Keeps track of recently learned hosts to prevent duplicate flowmods"

    def __init__(self, timeout):
        self.cache = {}
        self.logger = logging.getLogger("SS2HostCache")
        self.timeout = timeout

    def is_new_host(self, dpid, port, mac):
        "Check if the host/port combination is new and add the host entry"

        self.clean_entries()
        entry = self.cache.get((dpid, port, mac), None)
        if entry != None:
            entry.counter += 1
            return False

        entry = _HostCacheEntry(dpid, port, mac)
        self.cache[(dpid, port, mac)] = entry
        self.logger.debug("Learned %s, %s, %s", dpid, port, mac)
        return True

    def clean_entries(self):
        "Clean entries older than self.timeout"

        curtime = time.time()
        _cleaned_cache = {}
        for host in self.cache.values():
            if host.timestamp + self.timeout >= curtime:
                _cleaned_cache[(host.dpid, host.port, host.mac)] = host
            else:
                self.logger.debug("Unlearned %s, %s, %s after %s hits",
                                  host.dpid, host.port, host.mac, host.counter)

        self.cache = _cleaned_cache
