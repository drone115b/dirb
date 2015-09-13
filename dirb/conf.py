#####################################################################
#
# Copyright 2015 SpinVFX 
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License. 
# 
#####################################################################

import os

#######################################
#
# CLIENT CONFIGURATION:
#

# general configurations must start with DIRB

__default = {}
__default['DIRB_AUTHPATH'] = os.environ.get( 'DIRB_AUTHPATH', None )
__default['DIRB_SERVERS'] = [s.strip() for s in os.environ.get( 'DIRB_SERVERS', "" ).split(',')]


#######################################
#
# SERVER CONFIGURATION:
#

# server-only configurations must start with DIRBSERVER

__default_server = __default.copy()
__default_server[ 'DIRBSERVER_PERMISSIONS_EXPIRY' ] = int(os.environ.get( 'DIRBSERVER_PERMISSIONS_EXPIRY', 60 * 15 )) # 15 minutes

#######################################
#

def get_default_config( ):
    return __default.copy()


def get_default_server_config():
    return __default_server.copy()