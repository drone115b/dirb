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
from . import ds
from . import fs

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


  

class LocalClient( object ) :
  def __init__(self, compileddoc, startingpath ):
    self._doc = compileddoc
    self._root = startingpath

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

  def traverse( self, searcher ): # advanced API, not necessarily public
    ctx = ds.PathTraversalContext( {}, {}, self._root, {}, None, None, None )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    client = self
    return ds._traverse( searcher, rule, ctx, client )
  
  def get_bookmark_names( self ) :
    return self._doc['rules']['ROOT']['bookmarks']
  
  def get_bookmark_parameters( self, bookmark ):
    """returns the parameters required to find the bookmark.  A list of dictionaries.  Each dictionary is a set of parameters required to find the bookmark.  The key is the parameter name and the value determines which, if any, collection the parameter is associated with."""
    class SearcherBookmarks( object ):
      def __init__( self, dirstructure ) :
        self._store = []
        self._ds = dirstructure
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
    ctx = ds.PathTraversalContext( {}, {}, '', {}, None, None, None )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    ds._traverse( searcher, rule, ctx, self )  
    return searcher._store
  
  def search_paths( self, searchexpr ):
    """implies a query, with a specific predicate or filter to narrow the search, returns only paths that exist"""
    searcher = pathexpr.SearcherExists( self, searchexpr )
    ctx = ds.PathTraversalContext( {}, {}, self._root, {}, None, None, None )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    ds._traverse( searcher, rule, ctx, self )  
    return searcher._store
  
  def depict_paths( self, createexpr ):
    "this returns a not-exists path, but does not make a directory on disk"
    searcher = pathexpr.SearcherNotExists( self, createexpr )
    ctx = ds.PathTraversalContext( {}, {}, self._root, {}, None, None, None )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    ds._traverse( searcher, rule, ctx, self )  
    return searcher._store
  
  def get_path_context( self, targetpath ):
    "returns the path traversal context for the given path, works for real paths or depicted paths, will reject invalid paths, will accept paths deeper than what the structure knows about giving the deepest context it can"
    class SearcherPath( object ):
      def __init__( self, targetpath, client ) :
        self._splitpath = fs.split_path( targetpath )
        self._lensplitpath = len( self._splitpath )
        self._store = {} # this keeps matches, indexed by their depths
        self._ds = client
      def does_intersect_rule( self, rulectx ):
        return True
      def does_intersect_path( self, pathctx ):
        testpath = fs.split_path( pathctx.path )
        lentestpath = len(testpath)
        lenpath = min( self._lensplitpath, lentestpath )
        does_pass = self._splitpath[:lenpath] == testpath and lentestpath <= self._lensplitpath
        if does_pass and lentestpath not in self._store :
          # when we reach a new depth, we create a new entry in our storage
          self._store[lentestpath] = []
        return does_pass
      def test( self, pathctx, levelctx ):
        testpath = fs.split_path( pathctx.path )
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
          testpath = fs.split_path( pathctx.path )
          lenpath = len(testpath)
          if self._lensplitpath > lenpath:
            ret.add( self._splitpath[lenpath] )
        return ret
      
    searcher = SearcherPath( targetpath, self )
    ctx = ds.PathTraversalContext( {}, {}, self._root, {}, None, None, None )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    ds._traverse( searcher, rule, ctx, self )
    ret = ctx if targetpath == self._root else None
    if searcher._store :
      # all depths in the traversal needed to have a match, otherwise the path was not valid for the directory structure:
      if all( searcher._store[i] for i in searcher._store ):
        # we want to return the deepest match:
        key = max( searcher._store.keys() )
        assert 1 == len(searcher._store[key]), "Multiple targets found for single path (%s)" % targetpath
        ret = searcher._store[key][0]
    return ret

  def get_frontier_contexts( self, targetpath ):
    """given an existing path, returns the 'next' parameter to be defined, as well as the paths to which that parameter leads.
    necessary for UI development.
    returns a dictionary where the key is the parameter name, and the value is the list of directories associated with that parameter
    
    """
    """
    
    implementation details:
    set of parameters:
    calculate extra parameters
    calculate missing parameters
    if there are missing parameters, then cull the search
    if there is one extra parameter, then add it to the hits
    if there is zero extra parameters, then continue
    if there is more than one extra parameters, then cull the search
    
    """
    class SearcherPath( object ):
      def __init__( self, targetctx, client ) :
        self._splitpath = fs.split_path( targetctx.path )
        self._targetparam = set( targetctx.parameters.keys() )
        self._lensplitpath = len( self._splitpath )
        self._store = {}
        self._ds = client
      def does_intersect_rule( self, rulectx ):
        return True
      def does_intersect_path( self, pathctx ):
        testpath = fs.split_path( pathctx.path )
        lentestpath = len(testpath)
        lenpath = min( self._lensplitpath, lentestpath )
        extra_count = len( set( pathctx.parameters.keys() ) - self._targetparam )
        return self._splitpath[:lenpath] == testpath[:lenpath] and extra_count < 2
      def test( self, pathctx, levelctx ):
        path_set = set( pathctx.parameters.keys() )
        extra_param = path_set - self._targetparam
        extra_count = len( extra_param )
        missing_count = len( self._targetparam - path_set )
        testpath = fs.split_path( pathctx.path )
        lenpath = min( self._lensplitpath, len(testpath))
        if extra_count == 1 and ( not missing_count ) and levelctx.parameter:
          key = extra_param.pop()
          if not key in self._store:
            self._store[key] = []
          self._store[key].append( pathctx )
      def do_existing_paths( self ) :
        return True
      def get_parameters( self, key, levelctx, pathctxlist ):
        return None

    targetctx = self.get_path_context( targetpath )
    searcher = SearcherPath( targetctx, self )
    ctx = ds.PathTraversalContext( {}, {}, self._root, {}, None, None, None )
    rule = self._doc[ 'rules' ][ 'ROOT' ]
    ds._traverse( searcher, rule, ctx, self )  
    return searcher._store

      