#####################################################################
#
# Copyright 2015 Mayur Patel
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

#
# reference:
# http://stackoverflow.com/questions/4579908/cross-platform-splitting-of-path-in-python
# post by John Machin
#
def split_path(path):
  "returns a list of path parts, where the first element is the drive specification"
  def _split( path ):
    parts = []
    while True:
      newpath, tail = os.path.split(path)
      if newpath == path:
        assert not tail
        if path: parts.append(path)
        break
      parts.append(tail)
      path = newpath
    parts.reverse()
    return parts
  drive, drivelesspath = os.path.splitdrive( path )
  return [drive] + _split( drivelesspath )


def join_path( drive, *pathparts ): # @@ needs verification
  "concatentates a drive spec and a list of path parts into a complete path"
  return os.path.join( drive, *pathparts )

