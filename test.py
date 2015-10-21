#!/usr/bin/env python2.7

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

import dirb.ds as ds
import dirb.localclient as localclient
import dirb.sexpr as sexpr
import dirb.pathexpr as pathexpr

import unittest
import os

# ==========================================
class SimpleSexprTest(unittest.TestCase):
  # ----------------------------------------
  def test_identity( self ):
    e = "( and  (bookmark alpha) (parameter (key value) (key value) (key value)) )"
    self.assertEqual( sexpr.loads( e ), sexpr.loads(sexpr.dumps( sexpr.loads( e )))  )
    self.assertEqual( sexpr.loads( e ), ['and', ['bookmark', 'alpha'], ['parameter', ['key','value'], ['key','value'],['key','value']]]  )

  def test_escape_bracket( self ):
    e = r'("(name)" in bracket)'
    self.assertEqual( sexpr.loads( e ), ['(name)', 'in', 'bracket'] )
    
  def test_bracket( self ):
    e = r'(\(name\) in bracket)'
    self.assertEqual( sexpr.loads( e ), ['\\', ['name\\'], 'in', 'bracket'] )
  
  def test_quote( self ):
    e = '("(name) (value)\"\"" token2)'
    self.assertEqual( sexpr.loads( e ), ['(name) (value)\"\"', 'token2'] )
          
# ==========================================
# /<show>/sequence/<sequence>/<shot>/<dept>
# /<show>/asset/<assettype>/<asset>/<dept>
class SimpleLocalClientTest(unittest.TestCase):

  def setUp(self):
    self.dirlist = (
      '/tmp/dirbtest1/projects/',
      '/tmp/dirbtest1/projects/show',
      '/tmp/dirbtest1/projects/show/asset',
      '/tmp/dirbtest1/projects/show/asset/vehicle',
      '/tmp/dirbtest1/projects/show/asset/vehicle/car1',
      '/tmp/dirbtest1/projects/show/asset/vehicle/car1/lighting',
      '/tmp/dirbtest1/projects/show/sequence',
      '/tmp/dirbtest1/projects/show/sequence/aa',
      '/tmp/dirbtest1/projects/show/sequence/aa/xx',
      '/tmp/dirbtest1/projects/show/sequence/bb',
      '/tmp/dirbtest1/projects/show/sequence/bb/xx',
      '/tmp/dirbtest1/projects/show/sequence/bb/xx/animation',
      '/tmp/dirbtest1/projects/show/sequence/bb/xx/lighting',
      '/tmp/dirbtest1/projects/show/sequence/bb/yy',
      '/tmp/dirbtest1/projects/show/sequence/bb/zz',
      '/tmp/dirbtest1/projects/show/sequence/cc'
      )
    self.doc = ds.compile_dir_structure( { 
      'collections' : {"department":["animation","lighting"], "app":['katana','maya']},
      'rules' : {
          
        'ROOT' : [
                ['ParameterizedLevel', { "bookmarks":["showroot"], "key":'show'}],
                ['BranchLevel', {"rules":["sequence","asset"]}],
            ],
          
          
        'sequence' :[
                ['FixedLevel', {"name":'sequence'}],
                ['ParameterizedLevel', { "key":'sequence'}],
                ['ParameterizedLevel', { "key":'shot', "bookmarks":['shotroot']}],
                ['ParameterizedLevel', { "key":'dept', "collection":"department", 'bookmarks':['workarea']}]
            ],
          
          
        'asset' : [
                ['FixedLevel', {"name":'asset'}],
                ['ParameterizedLevel', { "key":'assettype'}],
                ['ParameterizedLevel', { "key":'asset', 'bookmarks':['assetroot']}],
                ['ParameterizedLevel', { "key":'dept', "collection":"department", 'bookmarks':['workarea']}]
            ]
        }
    } )
    self.d = localclient.LocalClient( self.doc, "/tmp/dirbtest1/projects" )
    for d in self.dirlist:
      if not os.path.isdir( d ):
        os.makedirs( d )

  # ----------------------------------------
  def test_simple_search(self):
    class ShotSearcher( object ) :
      def __init__( self ) :
        self.hold = []
      
      def does_intersect_rule( self, rulectx ):
        return 'shotroot' in rulectx.bookmarks
      
      def does_intersect_path( self, pathctx ):
        return True
      
      def test( self, pathctx, levelctx ):
        ret = 'shotroot' in levelctx.bookmarks
        if ret :
          self.hold.append( pathctx.path )
        return ret
            
      def do_existing_paths( self ):
        return False
    
      def get_parameters( self, key, levelctx, pathctxlist ) :
        if key == "sequence" :
          return ("SEQUENCE",)
        if key == "shot" :
          return ("SHOT",)
        if key == "show" :
          return ("SHOW",)
        if key == 'dept':
          return ( "animation","lighting" )
        return []
      
    s = ShotSearcher()
    self.d.traverse( s )
    self.assertEqual(s.hold, ['/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT'])
    
  # ----------------------------------------
  def test_bookmark_names(self):
    bookmarks = set( self.d.get_bookmark_names() )
    expected = set(('showroot','shotroot','assetroot','workarea'))
    self.assertEqual(bookmarks, expected)

  # ----------------------------------------
  def test_bookmark_parameters(self):
    found = self.d.get_bookmark_parameters('workarea')
    found = sorted( [ sorted(x.items()) for x in found ] )
    expected = [{'dept': 'department', 'show': None, 'shot': None, 'sequence': None}, {'dept': 'department', 'show': None, 'asset': None, 'assettype': None}]
    expected = sorted( [ sorted( x.items() ) for x in expected ] )
    self.assertEqual(found, expected)
    
  # ----------------------------------------
  def test_search_paths_and(self):
    searchexpr = '(and (bookmark shotroot) (parameters (show show)(shot xx)(sequence bb)))'
    foundlist = self.d.search_paths( searchexpr )
    self.assertEqual( len(foundlist), 1 )
    pathctx = foundlist[0]
    self.assertEqual( pathctx.path, '/tmp/dirbtest1/projects/show/sequence/bb/xx' )
    self.assertEqual( pathctx.parameters, {'show': 'show', 'shot': 'xx', 'sequence': 'bb'} )
    self.assertEqual( pathctx.bookmarks, ['shotroot'] )
    
  # ----------------------------------------
  def test_search_paths_multifinder_parameters(self):
    searchexpr = '(parameters (show show)(shot xx)(sequence bb))'
    foundlist = self.d.search_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/show/sequence/bb/xx/animation', 
      '/tmp/dirbtest1/projects/show/sequence/bb/xx/lighting', 
      '/tmp/dirbtest1/projects/show/sequence/bb/xx', 
      '/tmp/dirbtest1/projects/show/sequence/bb', 
      '/tmp/dirbtest1/projects/show/sequence', 
      '/tmp/dirbtest1/projects/show' ))
    self.assertEqual( foundlist, expected )

  # ----------------------------------------
  def test_search_paths_andor(self):
    searchexpr = '(and (bookmark workarea) (or (parameters (sequence bb))(parameters (asset car1))))'
    foundlist = self.d.search_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/show/asset/vehicle/car1/lighting',
      '/tmp/dirbtest1/projects/show/sequence/bb/xx/animation',
      '/tmp/dirbtest1/projects/show/sequence/bb/xx/lighting'))
    self.assertEqual( foundlist, expected )
  
  # ----------------------------------------
  def test_search_paths_multifinder_bookmarks(self):
    searchexpr = '(bookmark shotroot)'
    foundlist = self.d.search_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/show/sequence/aa/xx',
      '/tmp/dirbtest1/projects/show/sequence/bb/xx',
      '/tmp/dirbtest1/projects/show/sequence/bb/yy',
      '/tmp/dirbtest1/projects/show/sequence/bb/zz'))
    self.assertEqual( foundlist, expected )
    
  # ----------------------------------------
  def test_parameter_collect_parameter(self):
    found = pathexpr.create_parameter_collect( sexpr.loads( "(parameters (key1 value1) (key2 value2))" ))
    expected = {'key2': ('value2',), 'key1': ('value1',)}
    self.assertEqual( found, expected )
    
  # ----------------------------------------
  def test_parameter_collect_and(self):
    found = pathexpr.create_parameter_collect( sexpr.loads( "(and (parameters (key1 value1)) (parameters (key1 value1) (key2 value2)))" ))
    self.assertEqual( set(found['key1']), set(('value1',)) )
    self.assertEqual( set(found.keys()), set(('key1',)) )
    
  # ----------------------------------------
  def test_parameter_collect_or(self):
    found = pathexpr.create_parameter_collect( sexpr.loads( "(or (parameters (key1 value1)) (parameters (key2 value2)))" ))
    self.assertEqual( set(found['key1']), set(('value1',)) )
    self.assertEqual( set(found['key2']), set(('value2',)) )
    self.assertEqual( set(found.keys()), set(('key1','key2')) )
    
  # ----------------------------------------
  def test_depict_paths_rootonly(self):
    searchexpr = '(parameters (show SHOW))'
    foundlist = self.d.depict_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/SHOW',))
    self.assertEqual( foundlist, expected )
    
  # ----------------------------------------
  def test_depict_paths_collect_exception(self):
    searchexpr = '(parameters (show SHOW) (sequence SEQUENCE) (shot SHOT) (dept DEPT))'
    # this is not a valid path specification, because DEPT is not in the 'department' collection.
    self.assertRaises( KeyError, self.d.depict_paths, searchexpr )
    
  # ----------------------------------------
  def test_depict_paths_multiparam_multidir(self):
    searchexpr = '(parameters (show SHOW) (sequence SEQUENCE) (shot SHOT) (dept animation))'
    # "open" parameterizations like this will build the entire ancestor hierarchy
    foundlist = self.d.depict_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT',
      '/tmp/dirbtest1/projects/SHOW/asset',
      '/tmp/dirbtest1/projects/SHOW',
      '/tmp/dirbtest1/projects/SHOW/sequence',
      '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE',
      '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT/animation'))
    self.assertEqual( foundlist, expected )   
    
  # ----------------------------------------
  def test_depict_paths_multiparam_bookmark(self):
    searchexpr = '(and (bookmark workarea) (parameters (show SHOW) (sequence SEQUENCE) (shot SHOT) (dept animation)))'
    # the bookmark forces only workareas, not the entire hierarchy up to the parameterized leaf.
    foundlist = self.d.depict_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT/animation',))
    self.assertEqual( foundlist, expected )   
    
  # ----------------------------------------
  def test_depict_paths_andor(self):
    searchexpr = """
      (and 
        (bookmark workarea) 
        (or 
          (parameters (sequence SEQUENCE) (shot SHOT))
          (parameters (assettype TYPE) (asset ASSET))
          (parameters (show SHOW) (dept lighting))
        )
      )"""
    # the bookmark forces only workareas, not the entire hierarchy up to the parameterized leaf.
    foundlist = self.d.depict_paths( searchexpr )
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT/lighting',
      '/tmp/dirbtest1/projects/SHOW/asset/TYPE/ASSET/lighting'))
    self.assertEqual( foundlist, expected )
  
  # ----------------------------------------
  def test_get_path_context_realpath( self ):
    targetpath = '/tmp/dirbtest1/projects/show/asset/vehicle/car1/lighting'
    found = self.d.get_path_context( targetpath )
    expected = set( {'dept': 'lighting', 'assettype': 'vehicle', 'asset': 'car1', 'show': 'show'}.items() )
    self.assertEqual( found.path, targetpath )
    self.assertEqual( set(found.parameters.items()), expected )
    
  # ----------------------------------------
  def test_get_path_context_realpath2( self ):
    targetpath = '/tmp/dirbtest1/projects/show/sequence/bb'
    found = self.d.get_path_context( targetpath )
    expected = set( {'sequence': 'bb', 'show': 'show'}.items() )
    self.assertEqual( found.path, targetpath )
    self.assertEqual( set(found.parameters.items()), expected )
    
  # ----------------------------------------
  def test_get_path_context_depictedpath( self ):
    targetpath = '/tmp/dirbtest1/projects/newshow/asset/character/bigguy/animation'
    # this targetpath does not actually exist on disk, but can still be interrogated
    found = self.d.get_path_context( targetpath )
    expected = set( {'dept': 'animation', 'assettype': 'character', 'asset': 'bigguy', 'show': 'newshow'}.items() )
    self.assertEqual( found.path, targetpath )
    self.assertEqual( set(found.parameters.items()), expected )

  # ----------------------------------------
  def test_get_path_context_depictedfilename( self ):
    targetpath = '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT/animation/application/scenes/filename.scene'
    # it is okay to go deeper than the directory structure understands, it will return the deepest context it knows
    found = self.d.get_path_context( targetpath )
    expected = set( {'dept': 'animation', 'sequence': 'SEQUENCE', 'shot': 'SHOT', 'show': 'SHOW'}.items() )
    self.assertEqual( found.path, '/tmp/dirbtest1/projects/SHOW/sequence/SEQUENCE/SHOT/animation' )
    self.assertEqual( set(found.parameters.items()), expected )

  # ----------------------------------------
  def test_get_path_context_depictedpath_badcollection( self ):
    targetpath = '/tmp/dirbtest1/projects/falseshow/asset/set/castle/infantry'
    # department value in this targetpath is not a member of the department collection
    self.assertRaises( KeyError, self.d.get_path_context, targetpath )
  
  # ----------------------------------------
  def test_get_path_context_shallow( self ):
    targetpath = '/tmp/dirbtest1/projects/SHOW/editorial/workarea'
    # targetpath is not compatible with this directory structure
    found = self.d.get_path_context( targetpath )
    self.assertEqual( found.path, '/tmp/dirbtest1/projects/SHOW' )
    
  # ----------------------------------------
  def test_get_path_context_notvalidpath( self ):
    targetpath = '/tmp/dirbtest1/thing/SHOW'
    # targetpath is not compatible with this directory structure
    found = self.d.get_path_context( targetpath )
    self.assertEqual( found, None )
  
  # ----------------------------------------
  def test_get_frontier_contexts_root( self ):
    targetpath = '/tmp/dirbtest1/projects'
    found = self.d.get_frontier_contexts( targetpath )
    expected_keys = ["show"]
    expected_parameters = {'show':'show'}
    self.assertEqual( set(found.keys()), set(expected_keys) )
    self.assertEqual( len( found['show'] ), 1 )
    self.assertEqual( found['show'][0].parameters, expected_parameters )
    
  # ----------------------------------------
  def test_get_frontier_contexts_cluster( self ):
    targetpath = '/tmp/dirbtest1/projects/show/sequence'
    found = self.d.get_frontier_contexts( targetpath )
    expected_keys = ["sequence"]
    expected_parameters = set(['aa','bb','cc'])
    self.assertEqual( set(found.keys()), set(expected_keys) )
    self.assertEqual( len( found['sequence'] ), len(expected_parameters) )
    found_parameters = set( i.parameters['sequence'] for i in found['sequence'] )
    self.assertEqual( set(found_parameters), expected_parameters )

  # ----------------------------------------
  def test_get_frontier_contexts_branch( self ):
    targetpath = '/tmp/dirbtest1/projects/show'
    found = self.d.get_frontier_contexts( targetpath )
    expected_keys = set(["sequence",'assettype'])
    expected_parameters = set(['aa','bb','cc'])
    self.assertEqual( set(found.keys()), expected_keys )
    self.assertEqual( len( found['sequence'] ), len(expected_parameters) )
    found_parameters = set( i.parameters['sequence'] for i in found['sequence'] )
    self.assertEqual( set(found_parameters), expected_parameters )
    
    expected_parameters = set(['vehicle'])
    self.assertEqual( len( found['assettype'] ), len(expected_parameters) )
    found_parameters = set( i.parameters['assettype'] for i in found['assettype'] )
    self.assertEqual( set(found_parameters), expected_parameters )
    
  # ----------------------------------------
  def tearDown(self):
    # TODO should we remove the directories we created?
    pass
  
# ==========================================

class SimplePermissionsTest(unittest.TestCase): 

  def setUp(self):

    self.doc = ds.compile_dir_structure( { 
      'collections' : {"datatype":["caches","scenes","images"], 'assettype':['character','prop','vehicle','set']},
      'rules' : {
          
        'ROOT' : [
                ['BranchLevel', {'rules':['assets','shots']}],
                ],
        
        'shots' : [
                ['ParameterizedLevel', { "key":'datatype', "collection":"datatype", 'user':'root', 'group':'root', 'permissions':'rwxr-xr-x'}],
                ['ParameterizedLevel', { "key":'show'}],
                ['ParameterizedLevel', { "key":'sequence'}],
                ['ParameterizedLevel', { "key":'shot', 'bookmarks':['shotroot']}],
                ['ParameterizedLevel', { "key":'user', 'bookmarks':['workarea'], 'user':'(parameter user)', 'group':'shotdept', 'permissions':'rwxr-x---' }]
                ],                
          
          
        'assets' :[
                ['FixedLevel', {"name":'assets', 'user':'root', 'group':'root', 'permissions':'rwxr-xr-x'}],
                ['ParameterizedLevel', { "key":'show', 'group':'assetdept'}],
                ['ParameterizedLevel', { "key":'assettype', 'collection':'assettype'}],
                ['ParameterizedLevel', { "key":'assetname', 'bookmarks':['assetroot'] }],
                ['ParameterizedLevel', { "key":'user', 'bookmarks':['workarea'], 'user':'(parameter user)', 'permissions':'rwxr-x---' }]
            ]
        }
    } )
    self.d = localclient.LocalClient( self.doc, "/tmp/dirbtest1/projects" )

  # ----------------------------------------
  def test_simple_depict1(self):
    createexpr = '(and (bookmark workarea) (parameters (show diehard)(assettype vehicle)(assetname gunshipA)(user bwillis)))'
    foundlist = self.d.depict_paths( createexpr )
    self.assertEqual( 1, len(foundlist) )
    expected = { 'attributes':{}, 'parameters':{'assetname': 'gunshipA', 'assettype': 'vehicle', 'user': 'bwillis', 'show': 'diehard'}, 'path':'/tmp/dirbtest1/projects/assets/diehard/vehicle/gunshipA/bwillis', 'collections':{'assettype': 'assettype'}, 'user':'bwillis', 'group':'assetdept', 'permissions':488 }
    found = foundlist[0]
    self.assertEqual( found.attributes, expected['attributes'] )
    self.assertEqual( found.parameters, expected['parameters'] )
    self.assertEqual( found.path, expected['path'] )
    self.assertEqual( found.collections, expected['collections'] )
    self.assertEqual( found.user, expected['user'] )
    self.assertEqual( found.group, expected['group'] )
    self.assertEqual( found.permissions, expected['permissions'] )
    
  # ----------------------------------------
  def test_simple_depict2(self):
    createexpr = '(and (bookmark workarea) (parameters (datatype caches)(show diehard)(sequence QQQ)(shot TTT)(user bwillis)))'
    foundlist = self.d.depict_paths( createexpr )
    self.assertEqual( 1, len(foundlist) )
    expected = { 'attributes':{}, 'parameters':{'datatype': 'caches', 'sequence': 'QQQ', 'shot': 'TTT', 'user': 'bwillis', 'show': 'diehard'}, 'path':'/tmp/dirbtest1/projects/caches/diehard/QQQ/TTT/bwillis', 'collections':{'datatype': 'datatype'}, 'user':'bwillis', 'group':'shotdept', 'permissions':488 }
    found = foundlist[0]
    self.assertEqual( found.attributes, expected['attributes'] )
    self.assertEqual( found.parameters, expected['parameters'] )
    self.assertEqual( found.path, expected['path'] )
    self.assertEqual( found.collections, expected['collections'] )
    self.assertEqual( found.user, expected['user'] )
    self.assertEqual( found.group, expected['group'] )
    self.assertEqual( found.permissions, expected['permissions'] )
    
  # ----------------------------------------
  def test_simple_depict3(self):
    createexpr = '(and (bookmark shotroot) (parameters (datatype images)(show dh2)(sequence qqq)(shot ttt)(user arickman)))'
    foundlist = self.d.depict_paths( createexpr )
    self.assertEqual( 1, len(foundlist) )
    expected = { 'attributes':{}, 'parameters':{'datatype': 'images', 'show': 'dh2', 'shot': 'ttt', 'sequence': 'qqq'}, 'path':'/tmp/dirbtest1/projects/images/dh2/qqq/ttt', 'collections':{'datatype': 'datatype'}, 'user':'root', 'group':'root', 'permissions':493 }
    found = foundlist[0]
    self.assertEqual( found.attributes, expected['attributes'] )
    self.assertEqual( found.parameters, expected['parameters'] )
    self.assertEqual( found.path, expected['path'] )
    self.assertEqual( found.collections, expected['collections'] )
    self.assertEqual( found.user, expected['user'] )
    self.assertEqual( found.group, expected['group'] )
    self.assertEqual( found.permissions, expected['permissions'] )
    
  # ----------------------------------------
  def tearDown(self):
    pass
  

  
  
#####################################################################
if __name__ == '__main__':
    unittest.main()


