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

import stat

# 'rwxrwxrwx' for all permissions, '---------' for no permissions
def eval_ugo_expr( expr ):
  assert all( x in 'rwx-' for x in expr), 'Unknown characters in ugo expression (%s), expected r,w,x or -' % expr
  mod = 0
  
  if 'r' == expr[0]:
    mod |= stat.S_IRUSR
  else:
    assert '-' == expr[0], "Character 0 expected r or - in ugo expression (%s)" % expr
    pass
  
  if 'w' == expr[1]:
    mod |= stat.S_IWUSR
  else:
    assert '-' == expr[1], "Character 1 expected w or - in ugo expression (%s)" % expr
    pass
    
  if 'x' == expr[2]:
    mod |= stat.S_IXUSR
  else:
    assert '-' == expr[2], "Character 2 expected x or - in ugo expression (%s)" % expr
    pass
  
  
  if 'r' == expr[3]:
    mod |= stat.S_IRGRP
  else:
    assert '-' == expr[3], "Character 3 expected r or - in ugo expression (%s)" % expr
    pass
  
  if 'w' == expr[4]:
    mod |= stat.S_IWGRP
  else:
    assert '-' == expr[4], "Character 4 expected w or - in ugo expression (%s)" % expr
    pass
    
  if 'x' == expr[5]:
    mod |= stat.S_IXGRP
  else:
    assert '-' == expr[5], "Character 5 expected x or - in ugo expression (%s)" % expr
    pass
  
  
  if 'r' == expr[6]:
    mod |= stat.S_IROTH
  else:
    assert '-' == expr[6], "Character 6 expected r or - in ugo expression (%s)" % expr
    pass
  
  if 'w' == expr[7]:
    mod |= stat.S_IWOTH
  else:
    assert '-' == expr[7], "Character 7 expected w or - in ugo expression (%s)" % expr
    pass
    
  if 'x' == expr[8]:
    mod |= stat.S_IXOTH
  else:
    assert '-' == expr[8], "Character 8 expected x or - in ugo expression (%s)" % expr
    pass
  
  return mod
