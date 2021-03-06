# Copyright 2015 Cloudbase Solutions Srl
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
import os
import sys

from oslo_log import log as logging

from os_win._i18n import _, _LE
from os_win import exceptions
from os_win.utils import win32utils

if sys.platform == 'win32':
    kernel32 = ctypes.windll.kernel32
    import wmi

LOG = logging.getLogger(__name__)


class SMBUtils(object):
    def __init__(self):
        self._win32_utils = win32utils.Win32Utils()
        if sys.platform == "win32":
            self._smb_conn = wmi.WMI(moniker=r"root\Microsoft\Windows\SMB")

    def check_smb_mapping(self, share_path, remove_unavailable_mapping=False):
        mappings = self._smb_conn.Msft_SmbMapping(RemotePath=share_path)

        if not mappings:
            return False

        if os.path.exists(share_path):
            LOG.debug('Share already mounted: %s', share_path)
            return True
        else:
            LOG.debug('Share exists but is unavailable: %s ', share_path)
            if remove_unavailable_mapping:
                self.unmount_smb_share(share_path, force=True)
            return False

    def mount_smb_share(self, share_path, username=None, password=None):
        try:
            LOG.debug('Mounting share: %s', share_path)
            self._smb_conn.Msft_SmbMapping.Create(RemotePath=share_path,
                                                  UserName=username,
                                                  Password=password)
        except wmi.x_wmi as exc:
            err_msg = (_(
                'Unable to mount SMBFS share: %(share_path)s '
                'WMI exception: %(wmi_exc)s') % {'share_path': share_path,
                                                 'wmi_exc': exc})
            raise exceptions.SMBException(err_msg)

    def unmount_smb_share(self, share_path, force=False):
        mappings = self._smb_conn.Msft_SmbMapping(RemotePath=share_path)
        if not mappings:
            LOG.debug('Share %s is not mounted. Skipping unmount.',
                      share_path)

        for mapping in mappings:
            # Due to a bug in the WMI module, getting the output of
            # methods returning None will raise an AttributeError
            try:
                mapping.Remove(Force=force)
            except AttributeError:
                pass
            except wmi.x_wmi:
                # If this fails, a 'Generic Failure' exception is raised.
                # This happens even if we unforcefully unmount an in-use
                # share, for which reason we'll simply ignore it in this
                # case.
                if force:
                    raise exceptions.SMBException(
                        _("Could not unmount share: %s") % share_path)

    def get_share_capacity_info(self, share_path, ignore_errors=False):
        norm_path = os.path.abspath(share_path)

        total_bytes = ctypes.c_ulonglong(0)
        free_bytes = ctypes.c_ulonglong(0)

        try:
            self._win32_utils.run_and_check_output(
                kernel32.GetDiskFreeSpaceExW,
                ctypes.c_wchar_p(norm_path),
                None,
                ctypes.pointer(total_bytes),
                ctypes.pointer(free_bytes),
                kernel32_lib_func=True)
            return total_bytes.value, free_bytes.value
        except exceptions.Win32Exception as exc:
            LOG.error(_LE("Could not get share %(share_path)s capacity info. "
                          "Exception: %(exc)s"),
                      dict(share_path=share_path,
                           exc=exc))
            if ignore_errors:
                return 0, 0
            else:
                raise exc
