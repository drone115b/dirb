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

import itertools
import functools 
import fnmatch
import operator

from . import sexpr

# this implements the filter expression used by LocalClient.search_paths() 

_search_level_op = {}
_search_path_op = {}
_search_rule_op = {}

# this implements the filter expression used by LocalClient.depict_paths() 

_create_level_op = {}
_create_path_op = {}
_create_rule_op = {}
_create_pcollector_op = {} # need to collect the parameters, so you can navigate the theoretical structure.

# -------------------------------------
# semi-public interface:

def search_level_predicate( slist, pathctx, levelctx ):
  assert slist[0] in _search_level_op, "%s not a recognized search-expression keyword" % slist[0]
  return _search_level_op[slist[0]]( slist, pathctx, levelctx )

def search_path_predicate( slist, pathctx ):
  assert slist[0] in _search_path_op, "%s not a recognized search-expression keyword" % slist[0]
  return _search_path_op[slist[0]]( slist, pathctx )

def search_rule_predicate( slist, rulectx ):
  assert slist[0] in _search_rule_op, "%s not a recognized search-expression keyword" % slist[0]
  return _search_rule_op[slist[0]]( slist, rulectx )


def create_level_predicate( slist, pathctx, levelctx ):
  assert slist[0] in _create_level_op, "%s not a recognized create-expression keyword" % slist[0]
  return _create_level_op[slist[0]]( slist, pathctx, levelctx )

def create_path_predicate( slist, pathctx ):
  assert slist[0] in _create_path_op, "%s not a recognized create-expression keyword" % slist[0]
  return _create_path_op[slist[0]]( slist, pathctx )

def create_rule_predicate( slist, rulectx ):
  assert slist[0] in _create_rule_op, "%s not a recognized create-expression keyword" % slist[0]
  return _create_rule_op[slist[0]]( slist, rulectx )

def create_parameter_collect( slist ):
  assert slist[0] in _create_pcollector_op, "%s not a recognized create-expression keyword" % slist[0]
  return _create_pcollector_op[slist[0]]( slist )

# -------------------------------------

def _expose_search_level_op( name ):
  def _xl( fn ):
    _search_level_op[name] = fn
    return fn
  return _xl
  
def _expose_search_path_op( name ):
  def _xp( fn ):
    _search_path_op[name] = fn
    return fn
  return _xp

def _expose_search_rule_op( name ):
  def _xr( fn ):
    _search_rule_op[name] = fn
    return fn
  return _xr


def _expose_create_level_op( name ):
  def _xl( fn ):
    _create_level_op[name] = fn
    return fn
  return _xl
  
def _expose_create_path_op( name ):
  def _xp( fn ):
    _create_path_op[name] = fn
    return fn
  return _xp

def _expose_create_rule_op( name ):
  def _xr( fn ):
    _create_rule_op[name] = fn
    return fn
  return _xr

def _expose_create_pcollector_op( name ):
  def _xc( fn ):
    _create_pcollector_op[name] = fn
    return fn
  return _xc


# -------------------------------------

@_expose_search_level_op( "or" )
@_expose_create_level_op( "or" )
def _search_lvl_or( slist, pathctx, levelctx ):
  return any( search_level_predicate( x, pathctx, levelctx ) for x in slist[1:] )
  
@_expose_search_path_op( "or" )
@_expose_create_path_op( "or" )
def _search_path_or( slist, pathctx ):
  return any( search_path_predicate( x, pathctx ) for x in slist[1:] )
  
@_expose_search_rule_op( "or" )
@_expose_create_rule_op( "or" )
def _search_rule_or( slist, rulectx ):
  return any( search_rule_predicate( x, rulectx ) for x in slist[1:] )
  
@_expose_create_pcollector_op( "or" )  
def _create_pcollector_or( slist ):
  def _combine( *args ):
    "or operation amongst parameter dictionaries"
    ret = {}
    keys = set(itertools.chain( *[x.keys() for x in args ]))
    for key in keys:
      ret[key] = set(itertools.chain( *[x[key] for x in args if key in x ] ))
    return ret
  parameters = [create_parameter_collect( x ) for x in slist[1:]]
  parameters = [x for x in parameters if x is not None]
  return _combine( *parameters )

# -------------------------------------

@_expose_search_level_op( "and" )
@_expose_create_level_op( "and" )
def _search_lvl_and( slist, pathctx, levelctx ):
  return all( search_level_predicate( x, pathctx, levelctx ) for x in slist[1:] )
  
@_expose_search_path_op( "and" )
@_expose_create_path_op( "and" )
def _search_path_and( slist, pathctx ):
  return all( search_path_predicate( x, pathctx ) for x in slist[1:] )
  
@_expose_search_rule_op( "and" )
@_expose_create_rule_op( "and" )
def _search_rule_and( slist, rulectx ):
  return all( search_rule_predicate( x, rulectx ) for x in slist[1:] )

@_expose_create_pcollector_op( "and" )  
def _create_pcollector_and( slist ):
  def _combine( *args ):
    "and operation amongst parameter dictionaries"
    ret = {}
    keys = functools.reduce( lambda x, y : x & y, (set(x.keys()) for x in args))
    for key in keys:
      values = ( x[key] for x in args if key in x )
      ret[key] = functools.reduce( lambda x, y : x & y, (set(x) for x in values))
    return ret
  parameters = [create_parameter_collect( x ) for x in slist[1:]]
  parameters = [x for x in parameters if x is not None]
  return _combine( *parameters )

# -------------------------------------

def _search_path_parameters_base( slist, pathctx, fncmp ):
  valuedict = dict(slist[1:])
  for key in valuedict:
     if key in pathctx.parameters:
       if fncmp( pathctx.parameters[key], valuedict[key] ) :
         return False
  return True

@_expose_search_path_op("parameters")
def _search_path_parameters( slist, pathctx ):
  return _search_path_parameters_base( slist, pathctx, lambda a,b : not fnmatch.fnmatchcase(a,b) )

@_expose_create_path_op("parameters")  
def _create_path_parameters( slist, pathctx ):
  return _search_path_parameters_base( slist, pathctx, operator.ne )

@_expose_search_level_op("parameters")  
def _search_lvl_parameters( slist, pathctx, levelctx ):
  return _search_path_parameters_base( slist, pathctx, lambda a,b : not fnmatch.fnmatchcase(a,b) )

@_expose_create_level_op("parameters")  
def _create_lvl_parameters( slist, pathctx, levelctx ):
  return _search_path_parameters_base( slist, pathctx, operator.ne )
  
@_expose_search_rule_op("parameters")
@_expose_create_rule_op("parameters")
def _search_rule_parameters( slist, rulectx ):
  return any( x in rulectx.parameters for x in (y[0] for y in slist[1:]) )

@_expose_create_pcollector_op( "parameters" )  
def _create_pcollector_parameters( slist ):
  return dict((x[0], (x[1],)) for x in slist[1:])

# -------------------------------------

@_expose_search_path_op("-parameters")   
def _search_path_notparameters( slist, pathctx ):
  return _search_path_parameters_base( slist, pathctx, fnmatch.fnmatchcase )

@_expose_search_level_op("-parameters")  
def _search_lvl_notparameters( slist, pathctx, levelctx ):
  return _search_path_parameters_base( slist, pathctx, fnmatch.fnmatchcase )
  
@_expose_search_rule_op("-parameters")
def _search_rule_notparameters( slist, rulectx ):
  return True

# -------------------------------------

def _search_path_attributes_base( slist, pathctx, fncmp ):
  valuedict = dict(slist[1:])
  for key in valuedict:
     if key in pathctx.attributes:
       if fncmp( pathctx.attributes[key], valuedict[key] ):
         return False
  return True

@_expose_search_path_op("attributes")  
def _search_path_attributes( slist, pathctx ):
  return _search_path_attributes_base( slist, pathctx, lambda a,b : not fnmatch.fnmatchcase(a,b) )

@_expose_create_path_op("attributes")  
def _create_path_attributes( slist, pathctx ):
  return _search_path_attributes_base( slist, pathctx, operator.ne )

@_expose_search_level_op("attributes")  
def _search_lvl_attributes( slist, pathctx, levelctx ):
  return _search_path_attributes_base( slist, pathctx, lambda a,b : not fnmatch.fnmatchcase(a,b) )

@_expose_create_level_op("attributes")  
def _create_lvl_attributes( slist, pathctx, levelctx ):
  return _search_path_attributes_base( slist, pathctx, operator.ne )

@_expose_search_rule_op("attributes")
@_expose_create_rule_op("attributes")
def _search_rule_attributes( slist, rulectx ):
  return any( x in rulectx.attributes for x in (y[0] for y in slist[1:]) )

@_expose_create_pcollector_op( "attributes" )  
def _create_pcollector_attributes( slist ):
  return None

# -------------------------------------

@_expose_search_path_op("-attributes")  
def _search_path_notattributes( slist, pathctx ):
  return _search_path_attributes_base( slist, pathctx, fnmatch.fnmatchcase )

@_expose_search_level_op("-attributes")  
def _search_lvl_notattributes( slist, pathctx, levelctx ):
  return _search_path_attributes_base( slist, pathctx, fnmatch.fnmatchcase )
  
@_expose_search_rule_op("-attributes")
def _search_rule_notattributes( slist, rulectx ):
  return True

# -------------------------------------

@_expose_search_path_op("bookmark")
@_expose_create_path_op("bookmark")
def _search_path_bookmark( slist, pathctx ):
  return True

@_expose_search_level_op("bookmark")
@_expose_create_level_op("bookmark")
def _search_lvl_bookmark( slist, pathctx, levelctx ):
  return any( fnmatch.fnmatchcase( x, slist[1] ) for x in levelctx.bookmarks )

@_expose_search_rule_op("bookmark")
@_expose_create_rule_op("bookmark")
def _search_rule_bookmark( slist, rulectx ):
  return any( fnmatch.fnmatchcase( x, slist[1] ) for x in rulectx.bookmarks )

@_expose_create_pcollector_op( "bookmark" )  
def _create_pcollector_bookmark( slist ):
  return None

# -------------------------------------

@_expose_search_path_op("-bookmark")
def _search_path_notbookmark( slist, pathctx ):
  return True

@_expose_search_level_op("-bookmark")
def _search_lvl_notbookmark( slist, pathctx, levelctx ):
  return not any( fnmatch.fnmatchcase( x, slist[1] ) for x in levelctx.bookmarks )

@_expose_search_rule_op("-bookmark")
def _search_rule_notbookmark( slist, rulectx ):
  return True

# -------------------------------------


class SearcherExists( object ):
  def __init__( self, ds, expr ) :
    self._store = []
    self._ds = ds
    self._expr = sexpr.loads( expr )
  def does_intersect_rule( self, rulectx ):
    return search_rule_predicate( self._expr, rulectx )
  def does_intersect_path( self, pathctx ):
    return search_path_predicate( self._expr, pathctx )
  def test( self, pathctx, levelctx ):
    if search_level_predicate( self._expr, pathctx, levelctx ):
      self._store.append( pathctx )
  def do_existing_paths( self ) :
    return True
  def get_parameters( self, key, levelctx, pathctxlist ):
    return None


class SearcherNotExists( object ):
  def __init__( self, ds, expr ) :
    self._store = []
    self._ds = ds
    self._expr = sexpr.loads( expr )
    self._parameters = create_parameter_collect( self._expr )
    self._parameters = self._parameters if self._parameters else {}
  def does_intersect_rule( self, rulectx ):
    return create_rule_predicate( self._expr, rulectx )
  def does_intersect_path( self, pathctx ):
    return create_path_predicate( self._expr, pathctx )
  def test( self, pathctx, levelctx ):
    if create_level_predicate( self._expr, pathctx, levelctx ):
      self._store.append( pathctx )
  def do_existing_paths( self ) :
    return False
  def get_parameters( self, key, levelctx, pathctxlist ):
    return self._parameters[key] if key in self._parameters else None
