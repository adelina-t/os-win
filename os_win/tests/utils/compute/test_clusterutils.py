# Copyright 2016 Cloudbase Solutions Srl
# All Rights Reserved.
#
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

import mock

from os_win import exceptions
from os_win.tests import test_base
from os_win.utils.compute import clusterutils


class ClusterUtilsBaseTestCase(test_base.OsWinBaseTestCase):
    """Unit tests for the Hyper-V ClusterUtilsBase class."""

    def setUp(self):
        super(ClusterUtilsBaseTestCase, self).setUp()
        self._clusterutils = clusterutils.ClusterUtilsBase()
        self._clusterutils._conn_cluster = mock.MagicMock()
        self._clusterutils._cluster = mock.MagicMock()

    @mock.patch.object(clusterutils.ClusterUtilsBase,
                       '_get_cluster_nodes')
    def test_check_cluster_state_not_engough_nodes(self, mock_get_nodes):
        self.assertRaises(exceptions.HyperVClusterException,
                          self._clusterutils.check_cluster_state)

    def test_get_node_name(self):
        self._clusterutils._this_node = mock.sentinel.fake_node_name
        self.assertEqual(mock.sentinel.fake_node_name,
                         self._clusterutils.get_node_name())

    def test_get_cluster_nodes(self):
        node_list = [mock.sentinel.cluster_node1,
                     mock.sentinel.cluster_node2,
                     mock.sentinel.cluster_node3]
        fake_class = self._clusterutils._conn_cluster.MSCluster_ClusterToNode
        fake_class.return_value = node_list

        self.assertEqual(node_list, self._clusterutils._get_cluster_nodes())

    def test_get_cluster_vm_groups(self):
        vm_gr1 = mock.MagicMock(GroupType=self._clusterutils._VM_GROUP_TYPE)
        vm_gr2 = mock.MagicMock()
        vm_gr3 = mock.MagicMock(GroupType=self._clusterutils._VM_GROUP_TYPE)
        vm_group_list = [vm_gr1, vm_gr2, vm_gr3]
        fake_conn = self._clusterutils._conn_cluster
        fake_conn.MSCluster_ClusterToResourceGroup.return_value = vm_group_list

        res = list(self._clusterutils._get_vm_groups())

        self.assertIn(vm_gr1, res)
        self.assertNotIn(vm_gr2, res)
        self.assertIn(vm_gr3, res)


class ClusterUtilsTestCase(test_base.OsWinBaseTestCase):
    """Unit tests for the Hyper-V ClusterTest class."""

    _FAKE_VM_NAME = "fake_vm_name"
    _FAKE_RES_NAME = "fake_res_name"
    _FAKE_HOST = "fake_host"

    def setUp(self):
        super(ClusterUtilsTestCase, self).setUp()
        self._clusterutils = clusterutils.ClusterUtils()
        self._clusterutils._conn_cluster = mock.MagicMock()
        self._clusterutils._cluster = mock.MagicMock()

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_vm_group')
    def test_lookup_vm_group_check(self, mock_lookup_vm_group):
        mock_lookup_vm_group.return_value = mock.sentinel.fake_vm

        ret = self._clusterutils._lookup_vm_group_check(
            self._FAKE_VM_NAME)
        self.assertEqual(mock.sentinel.fake_vm, ret)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_vm_group')
    def test_lookup_vm_group_check_no_vm(self, mock_lookup_vm_group):
        mock_lookup_vm_group.return_value = None

        self.assertRaises(exceptions.HyperVClusterException,
                          self._clusterutils._lookup_vm_group_check,
                          self._FAKE_VM_NAME)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_res')
    def test_lookup_vm_group(self, mock_lookup_res):
        self._clusterutils._lookup_vm_group(self._FAKE_VM_NAME)
        mock_lookup_res.assert_called_once_with(
            self._clusterutils._conn_cluster.MSCluster_ResourceGroup,
            self._FAKE_VM_NAME)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_vm')
    def test_lookup_vm_check(self, mock_lookup_vm):
        mock_lookup_vm.return_value = mock.sentinel.fake_vm

        ret = self._clusterutils._lookup_vm_check(
            self._FAKE_VM_NAME)
        self.assertEqual(mock.sentinel.fake_vm, ret)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_vm')
    def test_lookup_vm_check_no_vm(self, mock_lookup_vm):
        mock_lookup_vm.return_value = None

        self.assertRaises(exceptions.HyperVVMNotFoundException,
                          self._clusterutils._lookup_vm_check,
                          self._FAKE_VM_NAME)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_res')
    def test_lookup_vm(self, mock_lookup_res):
        self._clusterutils._lookup_vm(self._FAKE_VM_NAME)
        mock_lookup_res.assert_called_once_with(
            self._clusterutils._conn_cluster.MSCluster_Resource,
            self._clusterutils._VM_BASE_NAME % self._FAKE_VM_NAME)

    def test_lookup_res_no_res(self):
        res_list = []
        resource_source = mock.MagicMock()
        resource_source.return_value = res_list

        self.assertIsNone(
            self._clusterutils._lookup_res(resource_source,
                                           self._FAKE_RES_NAME))
        resource_source.assert_called_once_with(
            Name=self._FAKE_RES_NAME)

    def test_lookup_res_duplicate_res(self):
        res_list = [mock.sentinel.r1,
                    mock.sentinel.r1]
        resource_source = mock.MagicMock()
        resource_source.return_value = res_list

        self.assertRaises(exceptions.HyperVClusterException,
                          self._clusterutils._lookup_res,
                          resource_source,
                          self._FAKE_RES_NAME)
        resource_source.assert_called_once_with(
            Name=self._FAKE_RES_NAME)

    def test_lookup_res(self):
        res_list = [mock.sentinel.r1]
        resource_source = mock.MagicMock()
        resource_source.return_value = res_list

        self.assertEqual(
            mock.sentinel.r1,
            self._clusterutils._lookup_res(resource_source,
                                           self._FAKE_RES_NAME))
        resource_source.assert_called_once_with(
            Name=self._FAKE_RES_NAME)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_get_cluster_nodes')
    def test_get_cluster_node_names(self, mock_get_cluster_nodes):
        cluster_nodes = [mock.Mock(Name='node1'),
                         mock.Mock(Name='node2')]
        mock_get_cluster_nodes.return_value = cluster_nodes

        ret = self._clusterutils.get_cluster_node_names()

        self.assertItemsEqual(['node1', 'node2'], ret)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_vm_group_check')
    def test_get_vm_host(self, mock_lookup_vm_group_check):
        owner_node = "fake_owner_node"
        vm = mock.Mock(OwnerNode=owner_node)
        mock_lookup_vm_group_check.return_value = vm

        self.assertEqual(
            owner_node,
            self._clusterutils.get_vm_host(self._FAKE_VM_NAME))

    @mock.patch.object(clusterutils.ClusterUtils, '_get_vm_groups')
    def test_list_instances(self, mock_get_vm_groups):
        mock_get_vm_groups.return_value = [mock.Mock(Name='vm1'),
                                           mock.Mock(Name='vm2')]
        ret = self._clusterutils.list_instances()
        self.assertItemsEqual(['vm1', 'vm2'], ret)

    @mock.patch.object(clusterutils.ClusterUtils, '_get_vm_groups')
    def test_list_instance_uuids(self, mock_get_vm_groups):
        mock_get_vm_groups.return_value = [mock.Mock(Id='uuid1'),
                                           mock.Mock(Id='uuid2')]
        ret = self._clusterutils.list_instance_uuids()
        self.assertItemsEqual(['uuid1', 'uuid2'], ret)

    @mock.patch.object(clusterutils.ClusterUtils,
                       '_lookup_vm_group_check')
    def test_add_vm_to_cluster(self, mock_lookup_vm_group_check):
        self._clusterutils._cluster.AddVirtualMachine = mock.MagicMock()
        vm_group = mock.Mock()
        mock_lookup_vm_group_check.return_value = vm_group

        self._clusterutils.add_vm_to_cluster(self._FAKE_VM_NAME)

        self.assertTrue(vm_group.PersistentState)
        self.assertEqual(vm_group.AutoFailbackType,
                         self._clusterutils._FAILBACK_TRUE)
        self.assertEqual(vm_group.FailbackWindowStart,
                         self._clusterutils._FAILBACK_WINDOW_MIN)
        self.assertEqual(vm_group.FailbackWindowEnd,
                         self._clusterutils._FAILBACK_WINDOW_MAX)
        vm_group.put.assert_called_once_with()

    @mock.patch.object(clusterutils.ClusterUtils, '_lookup_vm_check')
    def test_bring_online(self, mock_lookup_vm_check):
        vm = mock.MagicMock()
        mock_lookup_vm_check.return_value = vm

        self._clusterutils.bring_online(self._FAKE_VM_NAME)
        vm.BringOnline.assert_called_once_with()

    @mock.patch.object(clusterutils.ClusterUtils, '_lookup_vm')
    def test_take_offline(self, mock_lookup_vm):
        vm = mock.MagicMock()
        mock_lookup_vm.return_value = vm

        self._clusterutils.take_offline(self._FAKE_VM_NAME)
        vm.TakeOffline.assert_called_once_with()

    @mock.patch.object(clusterutils.ClusterUtils, '_lookup_vm_group')
    def test_delete(self, mock_lookup_vm_group):
        vm = mock.MagicMock()
        mock_lookup_vm_group.return_value = vm

        self._clusterutils.delete(self._FAKE_VM_NAME)
        vm.DestroyGroup.assert_called_once_with(
            self._clusterutils._DESTROY_GROUP)

    @mock.patch.object(clusterutils.ClusterUtils, '_lookup_vm')
    def test_vm_exists_true(self, mock_lookup_vm):
        vm = mock.MagicMock()
        mock_lookup_vm.return_value = vm

        self.assertTrue(self._clusterutils.vm_exists(self._FAKE_VM_NAME))

    @mock.patch.object(clusterutils.ClusterUtils, '_lookup_vm')
    def test_vm_exists_false(self, mock_lookup_vm):
        mock_lookup_vm.return_value = None

        self.assertFalse(self._clusterutils.vm_exists(self._FAKE_VM_NAME))

    @mock.patch.object(clusterutils.ClusterUtils, '_migrate_vm')
    def test_live_migrate_vm(self, mock_migrate_vm):
        self._clusterutils.live_migrate_vm(self._FAKE_VM_NAME,
                                           self._FAKE_HOST)
        mock_migrate_vm.assert_called_once_with(
            self._FAKE_VM_NAME, self._FAKE_HOST,
            self._clusterutils._LIVE_MIGRATION_TYPE)

    @mock.patch.object(clusterutils.ClusterUtils, '_lookup_vm_group_check')
    def test_migrate_vm(self, mock_lookup_vm_group_check):
        vm_group = mock.MagicMock()
        mock_lookup_vm_group_check.return_value = vm_group

        self._clusterutils._migrate_vm(
            self._FAKE_VM_NAME, self._FAKE_HOST,
            self._clusterutils._LIVE_MIGRATION_TYPE)

        vm_group.MoveToNewNodeParams.assert_called_once_with(
            self._clusterutils._IGNORE_LOCKED,
            self._FAKE_HOST,
            [self._clusterutils._LIVE_MIGRATION_TYPE])


class ClusterFailoverMonitorTestCase(test_base.OsWinBaseTestCase):
    """Unit tests for the Hyper-V ClusterFailoverMonitor class."""

    _FAKE_VM_NAME = 'instance-00000001'
    _FAKE_RESOURCEGROUP_NAME = 'Virtual Machine %s' % _FAKE_VM_NAME
    _FAKE_HOST = 'fake_host'

    def setUp(self):
        super(ClusterFailoverMonitorTestCase, self).setUp()
        self._clusterutils = clusterutils.ClusterFailoverMonitor()
        self._clusterutils._conn = mock.MagicMock()
        self._clusterutils._cluster = mock.MagicMock()
        self._clusterutils._vm_map = {}

    @mock.patch.object(clusterutils.ClusterFailoverMonitor,
                       '_list_vm_hosts')
    def test_update_vm_map(self, mock_list_vm_hosts):
        vm_map = [('vm1', 'vm_host1'), ('vm2', 'vm_host2')]
        mock_list_vm_hosts.return_value = vm_map

        self._clusterutils._update_vm_map()

        self.assertEqual('vm_host1', self._clusterutils._vm_map['vm1'])
        self.assertEqual('vm_host2', self._clusterutils._vm_map['vm2'])

    @mock.patch.object(clusterutils.ClusterFailoverMonitor,
                       '_get_vm_groups')
    def test_list_vm_hosts(self, mock_get_vm_groups):
        vm_groups = [mock.Mock(OwnerNode='owner1', Name='vm1'),
                     mock.Mock(OwnerNode='owner2', Name='vm2')]
        mock_get_vm_groups.return_value = vm_groups

        ret = self._clusterutils._list_vm_hosts()
        expected = [(r.Name, r.OwnerNode) for r in vm_groups]
        self.assertItemsEqual(expected, ret)

    def test_add_to_cluster_map(self):
        self._clusterutils._this_node = self._FAKE_HOST
        self._clusterutils.add_to_cluster_map(self._FAKE_VM_NAME)

        self.assertEqual(self._FAKE_HOST,
                         self._clusterutils._vm_map[self._FAKE_VM_NAME])

    def test_get_from_cluster_map(self):
        self._clusterutils._vm_map[self._FAKE_VM_NAME] = self._FAKE_HOST

        self.assertEqual(
            self._FAKE_HOST,
            self._clusterutils.get_from_cluster_map(self._FAKE_VM_NAME))

    def test_clear_from_cluster_map(self):
        self._clusterutils._vm_map = {self._FAKE_VM_NAME: self._FAKE_HOST}

        self._clusterutils.clear_from_cluster_map(self._FAKE_VM_NAME)

        self.assertNotIn(self._FAKE_VM_NAME,
                         self._clusterutils._vm_map.keys())

    def test_monitor_no_vm(self):
        self._clusterutils._watcher = mock.MagicMock()
        fake_wmi_object = mock.MagicMock(OwnerNode=self._FAKE_HOST,
                                         Name='Virtual Machine')
        self._clusterutils._watcher.return_value = fake_wmi_object
        fake_callback = mock.MagicMock()

        self._clusterutils.monitor(fake_callback)

        self._clusterutils._watcher.assert_called_once_with(
            self._clusterutils._WMI_EVENT_TIMEOUT_MS)
        fake_callback.assert_not_called()

    def test_monitor(self):
        self._clusterutils._watcher = mock.MagicMock()
        fake_wmi_object = mock.MagicMock(OwnerNode=self._FAKE_HOST,
                                         Name=self._FAKE_RESOURCEGROUP_NAME)
        self._clusterutils._watcher.return_value = fake_wmi_object
        fake_callback = mock.MagicMock()

        self._clusterutils.monitor(fake_callback)

        self._clusterutils._watcher.assert_called_once_with(
            self._clusterutils._WMI_EVENT_TIMEOUT_MS)
        fake_callback.assert_called_once_with(self._FAKE_VM_NAME,
                                              self._FAKE_HOST)
