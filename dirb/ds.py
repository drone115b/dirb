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

from . import pathexpr
from . import attrexpr
from . import ugoexpr

from . import fs

import copy
import collections
import itertools
import os
import glob



# A directory structure object:
#
# (1) has a schema,
# A set of rules which outline the tree-structure for the file system.
# One rule must be called "ROOT", but traversal can begin from anywhere
# and from any rule.
#
# (3) has collections, which connect with metadata
# It is handy to use collections as part of the directory structure,
# for example, to be able to use a departments list as a parameter
# for work area or publish area builds.
#
# (2) has globals, which are attributes that do not vary per-location.
#
#
# A directory location 
#   has an optional bookmark definition, which implicitly a parameterization by which the bookmark can be found.
#       in some ways, an bookmark is really just a special attribute tag.  
#       A bookmark can appear in different places, meaning that it can have multiple parameterizations
#       a bookmark is not inherited
#   has attributes, which can either be inherited down or not. (treeattribute, localattribute)
#   might be parameterized or not. a parameter is either unrestricted or restricted to a selection from a collection and
#   has a default owner and permissions.  The owner could be parameterized.
#
# Directory locations are stacked into rules as much as possible:
#   reduces the complexity of many kinds of structure schemas
#   allows optimizations to be placed strategically.
#   allows us to keep most of the directory structure as an explicit map/list,
#      converting on the absolutely bare essentials into additional complexity.
#
# Directory structure is meant to be flexible but not DYNAMIC!
#      You might want to change it a couple times a year, but not every day
#
# Need to resolve ambiguous paths by being strict with search order.
#     "fixed" directories should be listed first, in the reference list.
#     parameterized directories should be listed last (and ideally, there's only one!)
#




# before being compiled:
"""

{
  
  'collections' : {
    },
    
  'globals' : {},
  
  'rules' : {
  
    'ROOT' : [
        ['multiple', { 
            'key' : 'department'
            'bookmarks' : ['workarea'],
            'localattributes' : {},
            'treeattributes' : {},
            'user' : '(parameter user)',
            'group' : 'vfx',
            'permissions' : 'rwxr-xr-x' 
         }],
        
        ['directory', {
           'name' : 'value'
         }]
      
      ],
    
    'alternative' : [
      ],
    
    'rule2' : [
      ]
    }
}

"""

"""
a rule is a list of directory levels.
a compiled rule has:
   a set of bookmarks under it
   a set of parameters under it
   a set of attributes under it

Directory level types:
  fixed : one or more fixed names, not parameterized
     fields : bookmarks, local attrs, tree attrs, name, user, group, permissions
  branch : redirects to one or more other rules, IN ORDER, no special attributes of its own
     fields: rules
  parameterized : any number of parameterized directories, there is one key and potentially many values.
     fields : bookmarks, local attrs, tree attrs, key, collection, user group, permissions
     if there is an collection attribute, then the values are restricted.
  regex : can represent zero or more parameters, as defined by the groups in the expression.  Also good when
     there is a prefix or suffix or restrictions on the character set.
     fields: bookmarks, local attrs, tree attrs, pattern, collections, user, group, permissions
     regex is TODO
"""

FnLevel = {} # use of a singleton impairs ability to run multi-threaded, locks should be placed inside the level methods that need them.

# we use a class decorator here, instead of metaclasses for example,
# because what we really want is a dictionary of class instances (singletons actually),
# not some dictionary of classes, or other kind of class manipulation.
def register_level( cls ) :
  FnLevel[cls.__name__] = cls()
  return cls


class BaseLevel(object):
  def __init__(self):
    pass
  
  def validate( self, levelfields, path_list, client ): # for use during compile (?)
    return True
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, client ):
    return []
  
  def get_bookmarks( self, levelfields, doc ): # used during compile
    return set(levelfields['bookmarks'] if 'bookmarks' in levelfields else [])
  
  def get_attributes( self, levelfields, doc ): # used during compile
    keys = levelfields['localattributes'].keys() if 'localattributes' in levelfields else []
    keys.extend( levelfields['treeattributes'].keys() if 'treeattributes' in levelfields else [] )
    return set( keys )
    
  def get_parameters( self, levelfields, doc ): # used during compile
    return set([levelfields['key']] if 'key' in levelfields else [])



@register_level
class FixedLevel(BaseLevel) :
  def __init__(self):
    BaseLevel.__init__(self) # can't use super() because we instance the class before definition is complete!
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, client ):
    candidates = [(x, os.path.join(x.path, levelfields['name'])) for x in ctxlist]
    if searcher.do_existing_paths() :
      candidates = [(x, y) for x, y in candidates if os.path.isdir(y)]
    return candidates
    
  def get_parameters( self, levelfields, doc ): # used during compile
    return set()
  
@register_level
class BranchLevel(BaseLevel) :
  def __init__(self):
   BaseLevel.__init__(self) # can't use super() because we instance the class before definition is complete!
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, client):
    rulenames = levelfields['rules']
    for rulename, ctx in itertools.product( rulenames, ctxlist ) :
      rule = client.get_rule( rulename )
      _traverse( searcher, rule, ctx, client ) # indirect recursion
    return None
  
  def get_bookmarks( self, levelfields, doc ):
    bookmarks = set()
    rulenames = levelfields['rules']
    for rulename in rulenames :
      rule = doc['rules'][ rulename ]
      bookmarks |= get_rule_bookmarks(rule,doc)
    return bookmarks
  
  def get_attributes( self, levelfields, doc ):
    attributes = set()
    rulenames = levelfields['rules']
    for rulename in rulenames :
      rule = doc['rules'][ rulename ]
      attributes |= get_rule_attributes(rule,doc)
    return attributes
    
  def get_parameters( self, levelfields, doc ):
    parameters = set()
    rulenames = levelfields['rules']
    for rulename in rulenames :
      rule = doc['rules'][ rulename ]
      parameters |= get_rule_parameters(rule,doc)
    return parameters



@register_level
class ParameterizedLevel(BaseLevel) :
  def __init__(self):
    BaseLevel.__init__(self) # can't use super() because we instance the class before definition is complete!
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, client ):
    doexisting = searcher.do_existing_paths()
    dirlist = []
    
    if doexisting :
      
      for ictx in ctxlist:
        ctxdirs = glob.glob( os.path.join( ictx.path, '*' ))
        ctxdirs = ( x for x in ctxdirs if os.path.isdir( x ))
        
        if 'collection' in levelfields:
          coll = client.get_collection( levelfields['collection'] )
          ctxdirs = ( x for x in ctxdirs if os.path.split(x)[-1] in coll )
          
        dirlist.extend( (ictx, x) for x in ctxdirs )
      
    else:
      
      values = []
      if 'key' in levelfields:
        search_param = searcher.get_parameters(levelfields['key'], levelctx, ctxlist)
        if search_param:
          values.extend( x for x in search_param if x ) # eliminate None values
          
      if 'collection' in levelfields:
        coll = client.get_collection( levelfields['collection'] )
        bad_values = [x for x in values if x not in coll]
        if bad_values:
          raise KeyError( "Collection '%s' does not contain %s" % (levelfields['collection'], ','.join("'%s'" % x for x in bad_values)))
      
      for ctx, value in itertools.product( ctxlist, values ):
        dirlist.append((ctx, os.path.join( ctx.path, value )))
          
    return dirlist 
  
# -----------

def get_rule_bookmarks( levellist, doc ) : # used during compile
  ret = set()
  for level in levellist:
    leveltype = level[0]
    levelfields = level[1]
    ret |= FnLevel[leveltype].get_bookmarks( levelfields, doc)
  return ret
  
def get_rule_attributes( levellist, doc ): # used during compile
  ret = set()
  for level in levellist:
    leveltype = level[0]
    levelfields = level[1]
    ret |= FnLevel[leveltype].get_attributes( levelfields, doc)
  return ret

def get_rule_parameters( levellist, doc ): # used during compile
  ret = set()
  for level in levellist:
    leveltype = level[0]
    levelfields = level[1]
    ret |= FnLevel[leveltype].get_parameters( levelfields, doc)
  return ret  




RuleTraversalContext = collections.namedtuple( "RuleTraversalContext", ("bookmarks", "attributes", "parameters")) # elements of levels contained
PathTraversalContext = collections.namedtuple( "PathTraversalContext", ("attributes", "parameters", "path", "collections", "user", "group", "permissions") ) # includes attrs and params from current level
LevelTraversalContext = collections.namedtuple( "LevelTraversalContext", ( "bookmarks", "treeattributes", "localattributes", "parameter", "collection", "user", "group", "permissions" )) # elements of current level only



def _traverse( searcher, rule, ctx, client ):
  if searcher.does_intersect_rule( RuleTraversalContext( rule['bookmarks'], rule['attributes'], rule['parameters'] ) ):
    
    pathlist = [ctx]
    for leveltype, levelfields in rule[ 'levels' ]:
      
      # create new level context:
      levelbookmarks = levelfields['bookmarks'] if 'bookmarks' in levelfields else []
      leveltreeattr = levelfields['treeattributes'] if 'treeattributes' in levelfields else {}
      levellocalattr = levelfields['localattributes'] if 'localattributes' in levelfields else {}
      levelparameter = levelfields['key'] if 'key' in levelfields else None
      levelcollection = levelfields['collection'] if 'collection' in levelfields else None
      leveluser = levelfields['user'] if 'user' in levelfields else None
      levelgroup = levelfields['group'] if 'group' in levelfields else None
      levelpermissions = levelfields['permissions'] if 'permissions' in levelfields else None
      
      levelctx = LevelTraversalContext( levelbookmarks, leveltreeattr, levellocalattr, levelparameter, levelcollection, leveluser, levelgroup, levelpermissions )
      
      # get directories for this level
      ruletuples = FnLevel[ leveltype ].get_directories( levelctx, levelfields, searcher, pathlist, client )
      
      if not ruletuples:
        break # end for
      
      passedlist = []
      for ictx, dirname in ruletuples: # breadth-first search with pruning

        treeattr = ictx.attributes.copy() # shallow
        if 'treeattributes' in levelfields:
          treeattr.update( leveltreeattr )
          
        localattr = treeattr.copy() # shallow
        if 'localattributes' in levelfields:
          localattr.update( levellocalattr )
          
        parameters = ictx.parameters.copy() # shallow
        collections = ictx.collections.copy() # shallow
        if levelparameter :
          basename = os.path.basename( dirname )
          parameters[ levelparameter ] = basename
          if levelcollection:
            collections[ levelparameter ] = levelcollection
            
        user = attrexpr.eval_attribute_expr( leveluser, localattr, parameters ) if leveluser else ictx.user
        group = attrexpr.eval_attribute_expr( levelgroup, localattr, parameters ) if levelgroup else ictx.group
        permissions = ugoexpr.eval_ugo_expr( levelpermissions ) if levelpermissions else ictx.permissions
        
        newctx = PathTraversalContext( localattr, parameters, dirname, collections, user, group, permissions )
        test = searcher.does_intersect_path( newctx )
        if test:
          searcher.test( newctx, levelctx )
          newctx = PathTraversalContext( treeattr, parameters, dirname, collections, user, group, permissions ) # context that the children see & modify
          passedlist.append( newctx )
        
      pathlist = passedlist

  return

  
"""
a rule is a list of directory levels.
a compiled rule has:
   a set of bookmarks under it
   a set of parameters under it
   a set of attributes under it

Directory level types:
  fixed : one or more fixed names, not parameterized
     fields : bookmarks, local attrs, tree attrs, name
  branch : redirects to one or more other rules, IN ORDER, no special attributes of its own
     fields: rules
  parameterized : any number of parameterized directories, there is one key and potentially many values.
     fields : bookmarks, local attrs, tree attrs, key, collection,
     if there is an collection attribute, then the values are restricted.
     """

def compile_dir_structure( doc ):
    "returns a compiled version of the input document"
    ret ={ 'globals': {}, 'collections':{}, 'rules':{} }
    # copy globals:
    if 'globals' in doc:
      ret['globals'] = copy.deepcopy( doc['globals'] )
    # copy collections:
    if 'collections' in doc:
      ret['collections'] = copy.deepcopy( doc['collections'] )
    # copy rules:
    if 'rules' in doc:
      # a document rule is a key-value pair
      #    name of the rule is the key
      #    list of levels is the value.
      for rulename in doc['rules']:
        levellist = doc['rules'][rulename]
        ret['rules'][rulename] = {
          'levels' : copy.deepcopy( levellist ),
          'bookmarks' : tuple(get_rule_bookmarks(levellist, doc)),
          'parameters' : tuple(get_rule_parameters(levellist, doc)),
          'attributes' : tuple(get_rule_attributes(levellist, doc))
          }
    return ret

# -----------
