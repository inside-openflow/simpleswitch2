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
Base Application Class for SimpleSwitch 2.0 Apps
"""

from . import config, util
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib.packet import ethernet, ether_types as ether, packet
from ryu.ofproto import ofproto_v1_3

class SS2App(object):
    "Base methods for SS2 RyuApp classes"

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
        "Returns a list of all tables referenced in the current app's config"
        tables = []
        for key in self.config.keys():
            if key.startswith("table_"):
                tables.append(self.config[key])

        return tables

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
