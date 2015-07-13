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


import ds
import sexpr
import pathexpr
    
import unittest
import os

# ==========================================
class SimpleSexprTest(unittest.TestCase):
  # ----------------------------------------
  def test_identity( self ):
    e = "( and  (bookmark alpha) (parameter (key value) (key value) (key value)) )"
    self.assertEquals( sexpr.loads( e ), sexpr.loads(sexpr.dumps( sexpr.loads( e )))  )
    self.assertEquals( sexpr.loads( e ), ['and', ['bookmark', 'alpha'], ['parameter', ['key','value'], ['key','value'],['key','value']]]  )

  def test_escape_bracket( self ):
    e = r'("(name)" in bracket)'
    self.assertEquals( sexpr.loads( e ), ['(name)', 'in', 'bracket'] )
    
  def test_bracket( self ):
    e = r'(\(name\) in bracket)'
    self.assertEquals( sexpr.loads( e ), ['\\', ['name\\'], 'in', 'bracket'] )
  
  def test_quote( self ):
    e = '("(name) (value)\"\"" token2)'
    self.assertEquals( sexpr.loads( e ), ['(name) (value)\"\"', 'token2'] )
          
# ==========================================
# /<show>/sequence/<sequence>/<shot>/<dept>
# /<show>/asset/<assettype>/<asset>/<dept>
class SimpleLocalClientTest(unittest.TestCase):

  def setUp(self):
    self.dirlist = (
      '/tmp/dirbtests/projects/',
      '/tmp/dirbtests/projects/show',
      '/tmp/dirbtests/projects/show/asset',
      '/tmp/dirbtests/projects/show/asset/vehicle',
      '/tmp/dirbtests/projects/show/asset/vehicle/car1',
      '/tmp/dirbtests/projects/show/asset/vehicle/car1/lighting',
      '/tmp/dirbtests/projects/show/sequence',
      '/tmp/dirbtests/projects/show/sequence/aa',
      '/tmp/dirbtests/projects/show/sequence/aa/xx',
      '/tmp/dirbtests/projects/show/sequence/bb',
      '/tmp/dirbtests/projects/show/sequence/bb/xx',
      '/tmp/dirbtests/projects/show/sequence/bb/xx/animation',
      '/tmp/dirbtests/projects/show/sequence/bb/xx/lighting',
      '/tmp/dirbtests/projects/show/sequence/bb/yy',
      '/tmp/dirbtests/projects/show/sequence/bb/zz',
      '/tmp/dirbtests/projects/show/sequence/cc'
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
    self.d = ds.LocalClient( self.doc )
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
    self.d.traverse( s, '/tmp/dirbtests/projects' )
    self.assertEqual(s.hold, ['/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT'])
    
  # ----------------------------------------
  def test_bookmark_names(self):
    bookmarks = set( self.d.get_bookmark_names() )
    expected = set(('showroot','shotroot','assetroot','workarea'))
    self.assertEquals(bookmarks, expected)

  # ----------------------------------------
  def test_bookmark_parameters(self):
    found = sorted(self.d.get_bookmark_parameters('workarea'))
    expected = sorted([{'dept': 'department', 'show': None, 'shot': None, 'sequence': None}, {'dept': 'department', 'show': None, 'asset': None, 'assettype': None}])
    self.assertEquals(found, expected)
    
  # ----------------------------------------
  def test_search_paths_and(self):
    searchexpr = '(and (bookmark shotroot) (parameters (show show)(shot xx)(sequence bb)))'
    foundlist = self.d.search_paths( searchexpr, "/tmp/dirbtests/projects")
    self.assertEquals( len(foundlist), 1 )
    pathctx = foundlist[0]
    self.assertEquals( pathctx.path, '/tmp/dirbtests/projects/show/sequence/bb/xx' )
    self.assertEquals( pathctx.parameters, {'show': 'show', 'shot': 'xx', 'sequence': 'bb'} )
    
  # ----------------------------------------
  def test_search_paths_multifinder_parameters(self):
    searchexpr = '(parameters (show show)(shot xx)(sequence bb))'
    foundlist = self.d.search_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/show/sequence/bb/xx/animation', 
      '/tmp/dirbtests/projects/show/sequence/bb/xx/lighting', 
      '/tmp/dirbtests/projects/show/sequence/bb/xx', 
      '/tmp/dirbtests/projects/show/sequence/bb', 
      '/tmp/dirbtests/projects/show/sequence', 
      '/tmp/dirbtests/projects/show' ))
    self.assertEquals( foundlist, expected )

  # ----------------------------------------
  def test_search_paths_andor(self):
    searchexpr = '(and (bookmark workarea) (or (parameters (sequence bb))(parameters (asset car1))))'
    foundlist = self.d.search_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/show/asset/vehicle/car1/lighting',
      '/tmp/dirbtests/projects/show/sequence/bb/xx/animation',
      '/tmp/dirbtests/projects/show/sequence/bb/xx/lighting'))
    self.assertEquals( foundlist, expected )
  
  # ----------------------------------------
  def test_search_paths_multifinder_bookmarks(self):
    searchexpr = '(bookmark shotroot)'
    foundlist = self.d.search_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/show/sequence/aa/xx',
      '/tmp/dirbtests/projects/show/sequence/bb/xx',
      '/tmp/dirbtests/projects/show/sequence/bb/yy',
      '/tmp/dirbtests/projects/show/sequence/bb/zz'))
    self.assertEquals( foundlist, expected )
    
  # ----------------------------------------
  def test_parameter_collect_parameter(self):
    found = pathexpr.create_parameter_collect( sexpr.loads( "(parameters (key1 value1) (key2 value2))" ))
    expected = {'key2': ('value2',), 'key1': ('value1',)}
    self.assertEquals( found, expected )
    
  # ----------------------------------------
  def test_parameter_collect_and(self):
    found = pathexpr.create_parameter_collect( sexpr.loads( "(and (parameters (key1 value1)) (parameters (key1 value1) (key2 value2)))" ))
    self.assertEquals( set(found['key1']), set(('value1',)) )
    self.assertEquals( set(found.keys()), set(('key1',)) )
    
  # ----------------------------------------
  def test_parameter_collect_or(self):
    found = pathexpr.create_parameter_collect( sexpr.loads( "(or (parameters (key1 value1)) (parameters (key2 value2)))" ))
    self.assertEquals( set(found['key1']), set(('value1',)) )
    self.assertEquals( set(found['key2']), set(('value2',)) )
    self.assertEquals( set(found.keys()), set(('key1','key2')) )
    
  # ----------------------------------------
  def test_depict_paths_rootonly(self):
    searchexpr = '(parameters (show SHOW))'
    foundlist = self.d.depict_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/SHOW',))
    self.assertEquals( foundlist, expected )
    
  # ----------------------------------------
  def test_depict_paths_collect_exception(self):
    searchexpr = '(parameters (show SHOW) (sequence SEQUENCE) (shot SHOT) (dept DEPT))'
    # this is not a valid path specification, because DEPT is not in the 'department' collection.
    self.assertRaises( KeyError, self.d.depict_paths, searchexpr, "/tmp/dirbtests/projects")
    
  # ----------------------------------------
  def test_depict_paths_multiparam_multidir(self):
    searchexpr = '(parameters (show SHOW) (sequence SEQUENCE) (shot SHOT) (dept animation))'
    # "open" parameterizations like this will build the entire ancestor hierarchy
    foundlist = self.d.depict_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT',
      '/tmp/dirbtests/projects/SHOW/asset',
      '/tmp/dirbtests/projects/SHOW',
      '/tmp/dirbtests/projects/SHOW/sequence',
      '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE',
      '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT/animation'))
    self.assertEquals( foundlist, expected )   
    
  # ----------------------------------------
  def test_depict_paths_multiparam_bookmark(self):
    searchexpr = '(and (bookmark workarea) (parameters (show SHOW) (sequence SEQUENCE) (shot SHOT) (dept animation)))'
    # the bookmark forces only workareas, not the entire hierarchy up to the parameterized leaf.
    foundlist = self.d.depict_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT/animation',))
    self.assertEquals( foundlist, expected )   
    
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
    foundlist = self.d.depict_paths( searchexpr, "/tmp/dirbtests/projects")
    foundlist = set( x.path for x in foundlist )
    expected = set((
      '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT/lighting',
      '/tmp/dirbtests/projects/SHOW/asset/TYPE/ASSET/lighting'))
    self.assertEquals( foundlist, expected )
    
  # ----------------------------------------
  def test_get_path_context_realpath( self ):
    targetpath = '/tmp/dirbtests/projects/show/asset/vehicle/car1/lighting'
    found = self.d.get_path_context( targetpath, "/tmp/dirbtests/projects" )
    expected = set( {'dept': 'lighting', 'assettype': 'vehicle', 'asset': 'car1', 'show': 'show'}.items() )
    self.assertEquals( found.path, targetpath )
    self.assertEquals( set(found.parameters.items()), expected )
    
  # ----------------------------------------
  def test_get_path_context_depictedpath( self ):
    targetpath = '/tmp/dirbtests/projects/newshow/asset/character/bigguy/animation'
    # this targetpath does not actually exist on disk, but can still be interrogated
    found = self.d.get_path_context( targetpath, "/tmp/dirbtests/projects" )
    expected = set( {'dept': 'animation', 'assettype': 'character', 'asset': 'bigguy', 'show': 'newshow'}.items() )
    self.assertEquals( found.path, targetpath )
    self.assertEquals( set(found.parameters.items()), expected )

  # ----------------------------------------
  def test_get_path_context_depictedfilename( self ):
    targetpath = '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT/animation/application/scenes/filename.scene'
    # it is okay to go deeper than the directory structure understands, it will return the deepest context it knows
    found = self.d.get_path_context( targetpath, "/tmp/dirbtests/projects" )
    expected = set( {'dept': 'animation', 'sequence': 'SEQUENCE', 'shot': 'SHOT', 'show': 'SHOW'}.items() )
    self.assertEquals( found.path, '/tmp/dirbtests/projects/SHOW/sequence/SEQUENCE/SHOT/animation' )
    self.assertEquals( set(found.parameters.items()), expected )

  # ----------------------------------------
  def test_get_path_context_depictedpath_badcollection( self ):
    targetpath = '/tmp/dirbtests/projects/falseshow/asset/set/castle/infantry'
    # department value in this targetpath is not a member of the department collection
    self.assertRaises( KeyError, self.d.get_path_context, targetpath, "/tmp/dirbtests/projects" )

  # ----------------------------------------
  def test_get_path_context_notvalidpath( self ):
    targetpath = '/tmp/dirbtests/projects/SHOW/editorial/workarea'
    # targetpath is not compatible with this directory structure
    found = self.d.get_path_context( targetpath, "/tmp/dirbtests/projects" )
    self.assertEquals( found, None )
    
    ## @@ TBD

  # ----------------------------------------
  def tearDown(self):
    # @@ should we remove the directories we created?
    pass
  

if __name__ == '__main__':
    unittest.main()


