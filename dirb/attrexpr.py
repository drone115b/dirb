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

from . import sexpr


try:
  # python 2.x
  def isstring( s ) :
    return isinstance( s, basestring )
  isstring( "obviously a string" )
except NameError :
  # python 3.x
  def isstring( s ):
    return isinstance( s, str )
  


# will resolve the expression to a string
def eval_attribute_expr( expr, attributes, parameters ):
  e = sexpr.loads( expr )
  if isstring( e ):
    return e
  else:
    if 'attribute' == e[0] :
      assert e[1] in attributes, "Missing attribute %s in attribute expression %s" % (e[1], expr)
      return attributes[ e[1] ]
    elif 'parameter' == e[0] :
      assert e[1] in parameters, "Missing parameter %s in attribute expression %s" % (e[1], expr)
      return parameters[ e[1] ]
    elif 'env' == e[0] :
      assert e[1] in os.environ, "Missing environment variable %s in attribute expression %s" % (e[1], expr)
      return os.environ[ e[1] ]
    else:
      raise NameError( "Function %s not known in attribute expression %s" % (e[0], expr))
  return None
      
  
  