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
"Test basic L2 learning"

import unittest
import sys
from mininet.net import Mininet
from mininet.node import Ryu, OVSSwitch
from mininet.clean import cleanup
from mininet.topo import SingleSwitchTopo
from mininet.topolib import TreeTopo

# pylint: disable=C0111,R0201

def setUpModule():
    cleanup()

class SimpleTopoTestCase(unittest.TestCase):
    ryuParams = ['--verbose', 'ss2.core']
    def make_topo(self):
        return TreeTopo(2)

    def controller(self, name, **params):
        return Ryu(name, *self.ryuParams, **params)

    def setUp(self):
        self.net = Mininet(topo=self.make_topo(),
                           controller=self.controller,
                           switch=OVSSwitch,
                           waitConnected=True,
                           autoSetMacs=True)

        self.net.start()

    def tearDown(self):
        "Clean up the network"
        if sys.exc_info != (None, None, None):
            cleanup()
        else:
            self.net.stop()

class LearningTreeTestCase(SimpleTopoTestCase):
    def test_move(self):
        dropped = self.net.ping()
        self.assertEqual(dropped, 0)

        # h1 is initially connected to s2, move to s3
        h1 = self.net['h1']
        s3 = self.net['s3']
        h1.deleteIntfs()
        link = self.net.addLink(s3, h1, addr2="00:00:00:00:00:01")
        link.intf2.config(ip="10.0.0.1/8")
        s3.attach(link.intf1)

        # run ping again
        dropped = self.net.ping()
        self.assertEqual(dropped, 0)

class LearningSingleTestCase(SimpleTopoTestCase):
    def make_topo(self):
        return SingleSwitchTopo(2)

    def test_ping(self):
        dropped = self.net.ping()
        self.assertEqual(dropped, 0)

    def test_move(self):
        dropped = self.net.ping()
        self.assertEqual(dropped, 0)

        # move h1 to a different port on the switch
        h1 = self.net['h1']
        s1 = self.net['s1']
        h1.deleteIntfs()
        link = self.net.addLink(s1, h1, addr2="00:00:00:00:00:01")
        link.intf2.config(ip="10.0.0.1/8")
        s1.attach(link.intf1)

        # run ping again
        dropped = self.net.ping()
        self.assertEqual(dropped, 0)
