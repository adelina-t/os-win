# Copyright 2013 Cloudbase Solutions Srl
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

import ctypes
import socket
import sys

if sys.platform == 'win32':
    import wmi

from oslo_log import log as logging

from os_win._i18n import _, _LW
from os_win import constants
from os_win import exceptions

LOG = logging.getLogger(__name__)


class HostUtils(object):

    _windows_version = None

    _MSVM_PROCESSOR = 'Msvm_Processor'
    _MSVM_MEMORY = 'Msvm_Memory'
    _MSVM_NUMA_NODE = 'Msvm_NumaNode'

    _CENTRAL_PROCESSOR = 'Central Processor'

    _HOST_FORCED_REBOOT = 6
    _HOST_FORCED_SHUTDOWN = 12
    _DEFAULT_VM_GENERATION = constants.IMAGE_PROP_VM_GEN_1

    FEATURE_RDS_VIRTUALIZATION = 322
    FEATURE_MPIO = 57

    def __init__(self):
        self._virt_v2 = None
        if sys.platform == 'win32':
            self._conn_cimv2 = wmi.WMI(privileges=["Shutdown"])
            self._init_wmi_virt_conn()

    def _init_wmi_virt_conn(self):
        try:
            self._virt_v2 = wmi.WMI(moniker='//./root/virtualization/v2')
        except Exception:
            pass

    @property
    def _conn_virt(self):
        if self._virt_v2:
            return self._virt_v2
        raise exceptions.HyperVException(
            _("No connection to the 'root/virtualization/v2' WMI namespace."))

    def get_cpus_info(self):
        cpus = self._conn_cimv2.query("SELECT * FROM Win32_Processor "
                                      "WHERE ProcessorType = 3")
        cpus_list = []
        for cpu in cpus:
            cpu_info = {'Architecture': cpu.Architecture,
                        'Name': cpu.Name,
                        'Manufacturer': cpu.Manufacturer,
                        'NumberOfCores': cpu.NumberOfCores,
                        'NumberOfLogicalProcessors':
                        cpu.NumberOfLogicalProcessors}
            cpus_list.append(cpu_info)
        return cpus_list

    def is_cpu_feature_present(self, feature_key):
        return ctypes.windll.kernel32.IsProcessorFeaturePresent(feature_key)

    def get_memory_info(self):
        """Returns a tuple with total visible memory and free physical memory
        expressed in kB.
        """
        mem_info = self._conn_cimv2.query("SELECT TotalVisibleMemorySize, "
                                          "FreePhysicalMemory "
                                          "FROM win32_operatingsystem")[0]
        return (int(mem_info.TotalVisibleMemorySize),
                int(mem_info.FreePhysicalMemory))

    def get_volume_info(self, drive):
        """Returns a tuple with total size and free space
        expressed in bytes.
        """
        logical_disk = self._conn_cimv2.query("SELECT Size, FreeSpace "
                                              "FROM win32_logicaldisk "
                                              "WHERE DeviceID='%s'"
                                              % drive)[0]
        return (int(logical_disk.Size), int(logical_disk.FreeSpace))

    def check_min_windows_version(self, major, minor, build=0):
        version_str = self.get_windows_version()
        return list(map(int, version_str.split('.'))) >= [major, minor, build]

    def get_windows_version(self):
        if not HostUtils._windows_version:
            Win32_OperatingSystem = self._conn_cimv2.Win32_OperatingSystem()[0]
            HostUtils._windows_version = Win32_OperatingSystem.Version
        return HostUtils._windows_version

    def get_local_ips(self):
        addr_info = socket.getaddrinfo(socket.gethostname(), None, 0, 0, 0)
        # Returns IPv4 and IPv6 addresses, ordered by protocol family
        addr_info.sort()
        return [a[4][0] for a in addr_info]

    def get_host_tick_count64(self):
        return ctypes.windll.kernel32.GetTickCount64()

    def host_power_action(self, action):
        win32_os = self._conn_cimv2.Win32_OperatingSystem()[0]

        if action == constants.HOST_POWER_ACTION_SHUTDOWN:
            win32_os.Win32Shutdown(self._HOST_FORCED_SHUTDOWN)
        elif action == constants.HOST_POWER_ACTION_REBOOT:
            win32_os.Win32Shutdown(self._HOST_FORCED_REBOOT)
        else:
            raise NotImplementedError(
                _("Host %(action)s is not supported by the Hyper-V driver") %
                {"action": action})

    def get_supported_vm_types(self):
        """Get the supported Hyper-V VM generations.
        Hyper-V Generation 2 VMs are supported in Windows 8.1,
        Windows Server / Hyper-V Server 2012 R2 or newer.

        :returns: array of supported VM generations (ex. ['hyperv-gen1'])
        """
        if self.check_min_windows_version(6, 3):
            return [constants.IMAGE_PROP_VM_GEN_1,
                    constants.IMAGE_PROP_VM_GEN_2]
        else:
            return [constants.IMAGE_PROP_VM_GEN_1]

    def get_default_vm_generation(self):
        return self._DEFAULT_VM_GENERATION

    def check_server_feature(self, feature_id):
        return len(self._conn_cimv2.Win32_ServerFeature(ID=feature_id)) > 0

    def get_numa_nodes(self):
        numa_nodes = self._conn_virt.Msvm_NumaNode()
        nodes_info = []
        for node in numa_nodes:
            memory_info = self._get_numa_memory_info(node)
            if not memory_info:
                LOG.warning(_LW("Could not find memory information for NUMA "
                                "node. Skipping node measurements."))
                continue
            # Due to a bug in vmms, getting Msvm_Processor for the numa
            # node associators resulted in a vmms crash.
            # As an alternative to using associators we have to manually get
            # the related Msvm_Processor classes.
            # Msvm_HostedDependency is the association class between
            # Msvm_NumaNode and Msvm_Processor. We need to use this class to
            # relate the two because using associators on Msvm_Processor
            # will also result in a crash.
            processors = self._conn_virt.Msvm_Processor(['DeviceID'])
            numa_assoc = self._conn_virt.Msvm_HostedDependency(
                Antecedent=node.path_())
            numa_node_proc_paths = [item.Dependent for item in numa_assoc]
            cpu_info = self._get_numa_cpu_info(numa_node_proc_paths,
                                               processors)
            if not cpu_info:
                LOG.warning(_LW("Could not find CPU information for NUMA "
                                "node. Skipping node measurements."))
                continue

            node_info = {
                # NodeID has the format: Microsoft:PhysicalNode\<NODE_ID>
                'id': node.NodeID.split('\\')[-1],

                # memory block size is 1MB.
                'memory': memory_info.NumberOfBlocks,
                'memory_usage': node.CurrentlyConsumableMemoryBlocks,

                # DeviceID has the format: Microsoft:UUID\0\<DEV_ID>
                'cpuset': set([c.DeviceID.split('\\')[-1] for c in cpu_info]),
                # cpu_usage can be set, each CPU has a "LoadPercentage"
                'cpu_usage': 0,
            }

            nodes_info.append(node_info)

        return nodes_info

    def _get_numa_memory_info(self, node):
        memory_info = node.associators(wmi_result_class=self._MSVM_MEMORY)
        if memory_info:
            return memory_info[0]

    def _get_numa_cpu_info(self, numa_node_proc_paths, processors):
        cpu_info = []
        paths = [x.upper() for x in numa_node_proc_paths]
        for proc in processors:
            if proc.path_().upper() in paths:
                cpu_info.append(proc)

        return cpu_info
