# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import mox
import os
import pkg_resources
import subprocess
import unittest
import stat
import StringIO

from nose.plugins.attrib import attr

import heat.cloudinit.loguserdata as loguserdata


class FakeCiVersion():
    def __init__(self, version=None):
        self.version = version


class FakePOpen():
    def __init__(self, returncode=0):
        self.returncode = returncode

    def wait(self):
        pass


@attr(tag=['unit'])
@attr(speed='fast')
class LoguserdataTest(unittest.TestCase):

    def setUp(self):
        self.m = mox.Mox()
        self.m.StubOutWithMock(pkg_resources, 'get_distribution')
        self.m.StubOutWithMock(subprocess, 'Popen')
        self.m.StubOutWithMock(os, 'chmod')
        self.m.StubOutWithMock(os, 'makedirs')

    def tearDown(self):
        self.m.UnsetStubs()

    def test_ci_version(self):
        # too old versions
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.5.0'))
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.5.9'))

        # new enough versions
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.6.0'))
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.7.0'))
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('1.0'))
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('2.0'))

        self.m.ReplayAll()

        self.assertFalse(loguserdata.chk_ci_version())
        self.assertFalse(loguserdata.chk_ci_version())

        self.assertTrue(loguserdata.chk_ci_version())
        self.assertTrue(loguserdata.chk_ci_version())
        self.assertTrue(loguserdata.chk_ci_version())
        self.assertTrue(loguserdata.chk_ci_version())

        self.m.VerifyAll()

    def test_call(self):
        log = StringIO.StringIO()
        subprocess.Popen(
            ['echo', 'hi'],
            stderr=log,
            stdout=log).AndReturn(FakePOpen(0))

        self.m.ReplayAll()
        self.assertEqual(0, loguserdata.call(['echo', 'hi'], log))
        self.m.VerifyAll()

    def test_create_log(self):
        log_name = os.tmpnam()
        with loguserdata.create_log(log_name) as log:
            log.write('testing')

        log = open(log_name, 'r')
        self.assertEqual('testing', log.read())
        mode = os.stat(log_name).st_mode
        self.assertEqual(0600, stat.S_IMODE(mode))

    def test_main(self):

        log = StringIO.StringIO()
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.7.0'))
        os.chmod('/var/lib/cloud/data/cfn-userdata', 0700).AndReturn(None)
        subprocess.Popen(
            ['/var/lib/cloud/data/cfn-userdata'],
            stderr=log,
            stdout=log).AndReturn(FakePOpen(0))

        os.makedirs('/var/lib/heat', 0700).AndReturn(None)

        self.m.ReplayAll()
        loguserdata.main(log)
        self.m.VerifyAll()

    def test_main_fails(self):

        log = StringIO.StringIO()

        #fail on ci version
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.5.0'))

        #fail on execute cfn-userdata
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.7.0'))

        os.chmod('/var/lib/cloud/data/cfn-userdata', 0700).AndReturn(None)
        subprocess.Popen(
            ['/var/lib/cloud/data/cfn-userdata'],
            stderr=log,
            stdout=log).AndReturn(FakePOpen(-2))

        #fail on create directories
        pkg_resources.get_distribution('cloud-init').AndReturn(
            FakeCiVersion('0.7.0'))

        os.chmod('/var/lib/cloud/data/cfn-userdata', 0700).AndReturn(None)
        subprocess.Popen(
            ['/var/lib/cloud/data/cfn-userdata'],
            stderr=log,
            stdout=log).AndReturn(FakePOpen(0))
        os.makedirs('/var/lib/heat', 0700).AndRaise(OSError())

        self.m.ReplayAll()
        self.assertEqual(-1, loguserdata.main(log))
        self.assertEqual(-2, loguserdata.main(log))
        self.assertRaises(OSError, loguserdata.main, log)

        self.m.VerifyAll()
