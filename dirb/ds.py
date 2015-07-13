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

#
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
#       An attribute might reference a parameter or another attribute that is valid in that scope:
#           attribute['owner'] = '@attribute' or '$parameter' a double $$ passes a $ and a double @@ passes a @.
#       Value substitution should only be attempted on strings, of course.  Numbers and booleans, etc pass straight through.
#       This should be left for the user to do, resolving all attributes everywhere can be tricky. (?)
#       This whole scheme can be implemented by the user, using the get_properties() interface
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

# Do we need a permissive search as well as a specific search, to allow (for example) sequence areas to be found/built when building a shot area?
#
# Should there be a logfile extension to dirb, for dropping logs as operations execute?
#
# Should there be a compile stage for directory structure grammars, so that all the analysis (child bookmarks)
# etc takes place once, rather than on each load of the file?  It's also good for validation.  TODO: compare
# performance between python serialization, json.
#
#
# safe eval() is needed for search predicate.
# use 
# eval(expr_string,{"__builtins__":None}, ctx )
# 
# reference: http://lybniz2.sourceforge.net/safeeval.html
# tested and working in python 2.7.x and 3.4.x
#
# counter-argument: 
"""(t for t in 42 .__class__.__base__.__subclasses__() if t.__name__ ==
'LibraryLoader').next()((t for t in
__class__.__base__.__subclasses__() if t.__name__ ==
'CDLL').next()).msvcrt.system("SOMETHING MALICIOUS")"""
# apparently works on windows and some *nix
#
# exclude expressions that include double-underscore??

# before being compiled:
"""

{
  
  'collections' : {
    },
    
  'globals' : {},
  
  'rules' : {
  
    'ROOT' : [
        ['multiple', { 
            'parameters' : ['department']
            'bookmarks' : ['workarea'],
            'localattributes' : {},
            'treeattributes' : {},      
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
     fields : bookmarks, local attrs, tree attrs, name
  branch : redirects to one or more other rules, IN ORDER, no special attributes of its own
     fields: rules
  parameterized : any number of parameterized directories, there is one key and potentially many values.
     fields : bookmarks, local attrs, tree attrs, key, collection,
     if there is an collection attribute, then the values are restricted.
"""
import itertools
import os
import glob
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
  
  def validate( self, levelfields, path_list, ds ): # for use during compile (?)
    ## TBD
    return True
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, ds ):
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
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, ds ):
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
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, ds):
    rulenames = levelfields['rules']
    for rulename, ctx in itertools.product( rulenames, ctxlist ) :
      rule = ds.get_rule( rulename )
      _traverse( searcher, rule, ctx, ds ) # indirect recursion
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
  
  def get_directories( self, levelctx, levelfields, searcher, ctxlist, ds ):
    doexisting = searcher.do_existing_paths()
    dirlist = []
    
    if doexisting :
      
      for ictx in ctxlist:
        ctxdirs = glob.glob( os.path.join( ictx.path, '*' ))
        ctxdirs = ( x for x in ctxdirs if os.path.isdir( x ))
        
        if 'collection' in levelfields:
          coll = ds.get_collection( levelfields['collection'] )
          ctxdirs = ( x for x in ctxdirs if os.path.split(x)[-1] in coll )
          
        dirlist.extend( (ictx, x) for x in ctxdirs )
      
    else:
      
      values = []
      if 'key' in levelfields:
        search_param = searcher.get_parameters(levelfields['key'], levelctx, ctxlist)
        if search_param:
          values.extend( x for x in search_param if x ) # eliminate None values
          
      if 'collection' in levelfields:
        coll = ds.get_collection( levelfields['collection'] )
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
import copy
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

# a compiledrule is a dictionary with fields:
#    "bookmarks": set of bookmarks (under it)
#    "parameters" : set of parameters (keys only) (under it) 
#    "attributes" : set of attributes (keys only) (under it)
#    "levels" : tuples of tuples, (( "leveltype", {<levelfields>}),( "leveltype", {<levelfields>}),etc)
#    as traversal occurs, the bookmarks, parameter, attributes move from rules to the contexts as they resolve.
#

#
# A searcher has :
# does_intersect_rule( self, rulectx ) return bool if the rule might contain our target
# does_intersect_path( self, pathctx ) returns bool if the path might contain our target
# test( self, pathctx, levelctx ) to detemine whether this level is our target
# do_existing_paths() : bool, are we traversing real directories on disk, or is this theoretical?
# get_parameters( self, key, levelctx, pathctxlist ) : if this is a theoretical traversal, then the searcher needs to supply possible values, for each parameter key, to advance the search.


import collections
RuleTraversalContext = collections.namedtuple( "RuleTraversalContext", ("bookmarks", "attributes", "parameters")) # elements of levels contained
PathTraversalContext = collections.namedtuple( "PathTraversalContext", ("attributes", "parameters", "path", "collections") ) # includes attrs and params from current level
LevelTraversalContext = collections.namedtuple( "LevelTraversalContext", ( "bookmarks", "treeattributes", "localattributes", "parameters", "collection" )) # elements of current level only

#
# @@ ONE LAST TRAVERSAL FEATURE:
# would be great if the "path" was not a scalar, but rather a list/tuple of paths
# which were synonyms from the possibility of soft links being used.
# would be great if a search on a soft-link-resolved path "just worked."
#


def _traverse( searcher, rule, ctx, ds ):
  if searcher.does_intersect_rule( RuleTraversalContext( rule['bookmarks'], rule['attributes'], rule['parameters'] ) ):
    
    pathlist = [ctx]
    for level in rule[ 'levels' ]:
      
      # acquire level information:
      leveltype = level[0]
      levelfields = level[1]
      
      # create new level context:
      levelbookmarks = levelfields['bookmarks'] if 'bookmarks' in levelfields else []
      leveltreeattr = levelfields['treeattributes'] if 'treeattributes' in levelfields else {}
      levellocalattr = levelfields['localattributes'] if 'localattributes' in levelfields else {}
      levelparameter = levelfields['key'] if 'key' in levelfields else None
      levelcollection = levelfields['collection'] if 'collection' in levelfields else None
      levelctx = LevelTraversalContext( levelbookmarks, leveltreeattr, levellocalattr, levelparameter, levelcollection )
      
      # get directories for this level
      ruletuples = FnLevel[ leveltype ].get_directories( levelctx, levelfields, searcher, pathlist, ds )
      
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
          if levelparameter :
            parameters[ levelparameter ] = basename
            if levelcollection:
              collections[ levelparameter ] = levelcollection
            
        newctx = PathTraversalContext( localattr, parameters, dirname, collections )
        test = searcher.does_intersect_path( newctx )
        if test:
            searcher.test( newctx, levelctx )
            newctx = PathTraversalContext( treeattr, parameters, dirname, collections ) # context that the children see & modify
            passedlist.append( newctx )
        
      pathlist = passedlist

  return
  

import pathexpr # @@ from . import pathexpr
class LocalClient( object ) :
  def __init__(self, compileddoc ):
    self._doc = compileddoc

  def get_rule_names( self ):
    return self._doc['rules'].keys()
  
  def get_rule( self, rulename ): # advanced API, not necessarily public; returns compiled rule
    return self._doc['rules'][rulename] if rulename in self._doc['rules'] else None
  
  def get_collection_names( self ):
    return self._doc['collections'].keys()
  
  def get_collection( self, collectionname ) : 
    return self._doc['collections'][collectionname] if collectionname in self._doc['collections'] else None
  
  def get_global_names( self ):
    return self._doc['globals'].keys()
  
  def get_global( self, attrname ):
    return self._doc['globals'][attrname] if attrname in self._doc['globals'] else None

  def traverse( self, searcher, startingpath ): # advanced API, not necessarily public
    ctx = PathTraversalContext( {}, {}, startingpath, {} )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    ds = self
    return _traverse( searcher, rule, ctx, ds )
  
  def get_bookmark_names( self ) :
    return self._doc['rules']['ROOT']['bookmarks']
  
  def get_bookmark_parameters( self, bookmark ):
    """returns the parameters required to find the bookmark.  A list of dictionaries.  Each dictionary is a set of parameters required to find the bookmark.  The key is the parameter name and the value determines which, if any, collection the parameter is associated with."""
    class SearcherBookmarks( object ):
      def __init__( self, ds ) :
        self._store = []
        self._ds = ds
      def does_intersect_rule( self, rulectx ):
        return bookmark in rulectx.bookmarks
      def does_intersect_path( self, pathctx ):
        return True
      def test( self, pathctx, levelctx ):
        if bookmark in levelctx.bookmarks:
          found = ( (x,None) if x not in pathctx.collections else (x,pathctx.collections[x]) for x in pathctx.parameters.keys() )
          self._store.append( dict(found) )
      def do_existing_paths( self ) :
        return False
      def get_parameters( self, key, levelctx, pathctxlist ):
        if levelctx.collection:
          coll = self._ds.get_collection( levelctx.collection )
          return (coll[0],)
        else:
          return ('X',)
    searcher = SearcherBookmarks( self )
    ctx = PathTraversalContext( {}, {}, '', {} )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    _traverse( searcher, rule, ctx, self )  
    return searcher._store
  
  def search_paths( self, searchexpr, startingpath ):
    """implies a query, with a specific predicate or filter to narrow the search, returns only paths that exist"""
    searcher = pathexpr.SearcherExists( self, searchexpr )
    ctx = PathTraversalContext( {}, {}, startingpath, {} )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    _traverse( searcher, rule, ctx, self )  
    return searcher._store
  
  def depict_paths( self, createexpr, startingpath ):
    "this returns a not-exists path, but does not make a directory on disk"
    searcher = pathexpr.SearcherNotExists( self, createexpr )
    ctx = PathTraversalContext( {}, {}, startingpath, {} )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    _traverse( searcher, rule, ctx, self )  
    return searcher._store
  
  def get_path_context( self, targetpath, startingpath ):
    "returns the path traversal context for the given path, works for real paths or depicted paths, will reject invalid paths, will accept paths deeper than what the structure knows about giving the deepest context it can"
    
    def split_path( path ):
      ret = []
      head = path
      tail = path
      while tail :
        head, tail = os.path.split( head )
        if tail :
          ret.insert( 0, tail )
      return ret
    
    class SearcherPath( object ):
      def __init__( self, targetpath, ds ) :
        self._splitpath = split_path( targetpath )
        self._lensplitpath = len( self._splitpath )
        self._store = {} # this keeps matches, indexed by their depths
        self._ds = ds
      def does_intersect_rule( self, rulectx ):
        return True
      def does_intersect_path( self, pathctx ):
        testpath = split_path( pathctx.path )
        lentestpath = len(testpath)
        if lentestpath not in self._store :
          # when we reach a new depth, we create a new entry in our storage
          self._store[lentestpath] = []
        lenpath = min( self._lensplitpath, lentestpath )
        return self._splitpath[:lenpath] == testpath
      def test( self, pathctx, levelctx ):
        testpath = split_path( pathctx.path )
        lenpath = min( self._lensplitpath, len(testpath))
        if self._splitpath[:lenpath] == testpath[:lenpath] :
          # store hits at the depth they occur:
          self._store[lenpath].append( pathctx )
      def do_existing_paths( self ) :
        return False
      def get_parameters( self, key, levelctx, pathctxlist ):
        # we get parameters from the path itself
        ret = set()
        for pathctx in pathctxlist :
          testpath = split_path( pathctx.path )
          lenpath = len(testpath)
          if self._lensplitpath > lenpath:
            ret.add( self._splitpath[lenpath] )
        return ret
      
    searcher = SearcherPath( targetpath, self )
    ctx = PathTraversalContext( {}, {}, startingpath, {} )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    _traverse( searcher, rule, ctx, self )
    ret = None
    if searcher._store :
      # all depths in the traversal needed to have a match, otherwise the path was not valid for the directory structure:
      if all( searcher._store[i] for i in searcher._store ):
        # we want to return the deepest match:
        key = max( searcher._store.keys() )
        assert 1 == len(searcher._store[key]), "Multiple targets found for single path (%s)" % targetpath
        ret = searcher._store[key][0]
    return ret

  def get_frontier_parameters( self, targetpath, startingpath ): # @@ WIP
    "returns the path traversal context for the given path"
    """
    set of parameters:
    calculate extra parameters
    calculate missing parameters
    if there are missing parameters, then cull the search
    if there is one extra parameter, then add it to the hits
    if there is zero extra parameters, then continue
    if there is more than one extra parameters, then cull the search
    
    How do we handle the differences between searching a real path and searching a depicted path for frontier parameters?
    """
    class SearcherPath( object ):
      def __init__( self, targetpath, ds ) :
        self._splitpath = split_path( targetpath )
        self._store = []
        self._ds = ds
      def does_intersect_rule( self, rulectx ):
        return True
      def does_intersect_path( self, pathctx ):
        testpath = split_path( pathctx.path )
        lenpath = len(testpath)
        return self._splitpath[:lenpath] == testpath
      def test( self, pathctx, levelctx ):
        
        
        
        testpath = split_path( pathctx.path )
        if testpath == self._splitpath :
          self._store.append( pathctx )
      def do_existing_paths( self ) :
        return True
      def get_parameters( self, key, levelctx, pathctxlist ):
        return None
    searcher = SearcherPath( targetpath, self )
    ctx = PathTraversalContext( {}, {}, startingpath, {} )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    _traverse( searcher, rule, ctx, self )  
    return searcher._store

"""
  

    get_frontier_parameters( filter/predicate, parameters, startingpath, starting rule='ROOT' )
    # if the parameters values stop immediately at a location, then list parameters needed to traverse further.
    # if a location is reached, but there are more parameters to be used, then do not list the location.
    # predicate allows the traversal (from the very beginning) to prune areas not of interest
    # this is essentially how you implement a navigation UI utop an abstracted directory structure
    
    
    get_frontier_parameters(root_dir, directory_structure, nav_params={}, skip_params=[], skip_tags=[]):
    
    

    predicate language:
      ["parameters", {'show':'exp1','shot':thing,'department':thing}]
      ["parameters-match", {'show':'dom*'}] # use fnmatch?
      ["attributes", {'smell':'stinky'}]   # ATTRIBUTES PREDICATES ONLY WORK IF THE ATTRIBUTE IS A STRICT KEY-VALUE PAIR!
      ["attributes-match", {'show':'dom*'}] # a has-attributes operations may be ['attributes-match', {'key':'*'} ]  # ATTRIBUTES PREDICATES ONLY WORK IF THE ATTRIBUTE IS A STRICT KEY-VALUE PAIR!
      ['attributes-below', ['key','key']]
      ["bookmarks", ["shot"]]
      ['bookmarks-above', [value,value]]
      ['bookmarks-below', [value,value]]
      ["and", [subpredicate, subpredicate]]
      ["or", [subpredicate, subpredicate]]
      ['not', subpredicate]
      ['pass' ] # return true for everything!
      
      
      ['and', ['not', 'bookmarks', ['shot']], ['not', 'above-bookmarks', ['shot']]] # predicate to prune paths not leading to a shot
      
      
      ['and', ['bookmarks',['shot']], ['parameters', {}]]
      
      
import re

_security_concerns = (
    re.compile( "\.(\s)*_" ), # reference a protected member
    re.compile( "__" ), # reference a private member
)

def _safe_eval( expr, env ):
  "Not exactly the safest in the world, but if you fear malicious attacks, then this is probably not the product for you"
  if any( x.search(expr) for x in _security_concerns ):
    raise LookupError, "Potential security violation in expression (%s), aborted" % expr
  else:
    return eval( expr, { '__builtins__' : None }, env )


We should have a "system lock" where root can create (and own) a file of a given name
(how about "_sys_lock_" and dirb will not create directories underneath that level.
Do we need a "_read_lock_" to prevent reads below a certain level?  Does that mean
we need a "_read_lock_" and "_write_lock_" ??
      
Eliminate the capability of one directory being parameterized two different ways.  One directory, one key only.
      
      """
      