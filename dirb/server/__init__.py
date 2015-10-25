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

try: # version-proof
    import xmlrpclib as xmlrpc_lib
except ImportError :
    import xmlrpc.client as xmlrpc_lib
    
# -------------------------------------------------------------------    

from .. import localclient
from .. import fs
from .. import conf
from .. import auth
from .. import ds

# -------------------------------------------------------------------    

import stat
import grp
import pwd
import os
import logging
import inspect
import functools
import copy
import threading
import random
import socket
import base64
import datetime
import codecs

# -------------------------------------------------------------------    
# things that we probably don't want to expose to configuration:

NONCE_EXPIRY = 60 # seconds
NONCE_CACHE_LIMIT = 4096

DEFAULT_UID = 0
DEFAULT_GID = 0
DEFAULT_PERMISSIONS = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH

# -------------------------------------------------------------------    
#    
# Implements a XML-RPC client class 
# with decorators to autopopulate from the
# definition of the server:
#
# Unfortunately, XMLRPC does not support optional arguments, so this complicates
# our attempts at simplifying the parameters associated with authentication.
#
class RemoteClient( localclient.LocalClient ) :
  
    def __init__( self, confdict, compileddoc, startingpath, notifier=None ):
        server_list = [x.strip() for x in confdict['DIRB_SERVERS'].split(',')]
        assert len(server_list) > 0
        self._server_list = server_list
        self._server_bound = len(server_list)
        assert( self._server_bound )
        self._server_num = random.randint( 0, self._server_bound-1) 
        self._notifier = notifier
        self._conf = confdict
        super(RemoteClient, self).__init__( compileddoc, startingpath )

    # ===========================================
          
    def _pick_one( self ):
        # round robin across the servers
        ret = self._server_list[ self._server_num ]
        self._server_num += 1
        self._server_num = 0 if self._server_num == self._server_bound else self._server_num
        return ret
    
    # ===========================================
    
    def _get_user( self, user_index, args, kwargs ):
        if len( args ) > user_index :
            if args[ user_index ] :
                return args[ user_index ]
        else:
            if 'user' in kwargs:
                if kwargs['user']:
                    return kwargs['user']

        return auth.get_username()
            
    # ===========================================
    
    def _set_user( self, user_index, user, args, kwargs ):
        newargs = args
        newkw = kwargs
        if len( args ) > user_index :
            newargs = list( args )
            newargs[ user_index ] = user
        elif len( args ) == user_index :
            newargs = list( args ) + [ user ]
        else:
            # xmlrpc does not support kwargs, so we cannot use them
            raise TypeError( 'Unable to attach authentication argument' )
        
        return newargs, newkw

    # ===========================================
    
    def _set_compileddoc( self, doc_index, doc, args, kwargs ):
        newargs = args
        newkw = kwargs
        if doc_index is not None:
            if len( args ) > doc_index :
                newargs = list( args )
                newargs[ doc_index ] = doc
            elif len( args ) == doc_index :
                newargs = list( args ) + [ doc ]
            elif len( args) < doc_index :
                delta = doc_index - len( args )
                newargs = list( args ) + [ None ] * delta + [ doc ]
            else:
                # xmlrpc does not support kwargs, so we cannot use them
                raise TypeError( 'Unable to attach compiled schema document' )
        
        return newargs, newkw
      
    # ===========================================
    
    def _set_startingpath( self, path_index, path, args, kwargs ):
        newargs = args
        newkw = kwargs
        if path_index is not None:
            if len( args ) > path_index :
                newargs = list( args )
                newargs[ path_index ] = path
            elif len( args ) == path_index :
                newargs = list( args ) + [ path ]
            elif len( args) < path_index :
                delta = path_index - len( args )
                newargs = list( args ) + [ None ] * delta + [ path ]
            else:
                # xmlrpc does not support kwargs, so we cannot use them
                raise TypeError( 'Unable to attach starting path' )
        
        return newargs, newkw
      
    # ===========================================
    
    def _replace_args( self, server, method, args, kwargs ):
        "as a convenience, we can automagically fill in some args that the server method requires"
        argspec = inspect.getargspec(method)
        user_index = argspec.args.index( 'user' ) - 1 
        doc_index = argspec.args.index( 'compileddoc' ) - 1 if 'compileddoc' in argspec.args else None
        path_index = argspec.args.index( 'startingpath' ) - 1 if 'startingpath' in argspec.args else None
        
        # security protocol replaces username with a full user-credential object:
        servernonce = server.get_nonce()
        username = self._get_user( user_index, args, kwargs )
        user = tuple( auth.get_user_credentials( username, self._conf, servernonce ))
        newargs, newkw = self._set_user( user_index, user, args, kwargs )
        
        # attach the compile document to the call, when appropriate:
        # attach the starting path to the call, will very frequently pair with the compiled document
        if doc_index is not None:
            newargs, newkw = self._set_compileddoc( doc_index, self._doc, newargs, newkw )
        if path_index is not None:
            newargs, newkw = self._set_startingpath( path_index, self._root, newargs, newkw )
            
        return newargs, newkw
    
    # ===========================================
    
    # if a server fails, then send email and remove it from the list!
    def _call_one( self, method, *args, **kwargs ):
        server = self._pick_one()
        ret = None
        try:
            try: 
                p = xmlrpc_lib.ServerProxy(server, allow_none=True, use_builtin_types=True )
            except TypeError :
                p = xmlrpc_lib.ServerProxy(server, allow_none=True )

            name = method.__name__
            
            # replace any arguments that we should:
            newargs, newkw = self._replace_args( p, method, args, kwargs )
            
            # Be careful here, if you mess this call up, you'll be calling the
            # local definition of the server method, not the method on the remote server!
            ret = p.__getattr__(name)(*newargs, **newkw) # do the function call
            
        except socket.error :
            if self._notifier :
                self._notifier( server ) # flash the red lights
            self._server_list.remove( server )
            self._server_bound = len( self._server_list )
            self._server_num = 0
            if not self._server_list:
                raise # pass the socket.error on up
            return self._call_one( method, *args, **kwargs )
        return ret

    # ===========================================
        
    def _call_all( self, method, *args, **kwargs ):
        ret = {}
        
        # would be lovely to execute in parallel:
        for server in self._server_list :
            try:
                try: 
                    p = xmlrpc_lib.ServerProxy(server, allow_none=True, use_builtin_types=True )
                except TypeError :
                    p = xmlrpc_lib.ServerProxy(server, allow_none=True )
                name = method.__name__
                
                # replace any arguments that we should:
                newargs, newkw = self._replace_args( p, method, args, kwargs )
                
                # Be careful here, if you mess this call up, you'll be calling the
                # local definition of the server method, not the method on the remote server!
                ret[ server ] = p.__getattr__(name)( *newargs, **newkw) # do the function call

            except socket.error :
                if self._notifier :
                    self._notifier( server ) # flash the red lights
                self._server_list.remove( server )
                self._server_bound = len( self._server_list )
                self._server_num = 0
                raise # pass the socket.error on up

        return ret

    # ===========================================
      
    @classmethod
    def _rpc_one( cls, fn ):
        def api( client, *args, **kwargs ):
            return client._call_one( fn, *args, **kwargs )
        
        api.__doc__ = fn.__doc__
        setattr( cls, fn.__name__, api )  
        return fn

    # ===========================================
      
    @classmethod
    def _rpc_all( cls, fn ):
        def api( client, *args, **kwargs ):
            return client._call_all( fn, *args, **kwargs )
            
        api.__doc__ = fn.__doc__
        setattr( cls, fn.__name__, api )  
        return fn

    # ===========================================
    
    @classmethod
    def _rpc_specific( cls, fn ):
        argspec = inspect.getargspec(fn)
        server_index = argspec.args.index( 'server' ) - 1
        
        def api( client, *args, **kwargs ):
            server = args[server_index]

            try: 
                p = xmlrpc_lib.ServerProxy(server, allow_none=True, use_builtin_types=True )
            except TypeError :
                p = xmlrpc_lib.ServerProxy(server, allow_none=True )

            method = p.__getattr__(fn.__name__)
            
            # replace any arguments that we should:
            newargs, newkw = client._replace_args( p, method, args, kwargs )

            # Be careful here, if you mess this call up, you'll be calling the
            # local definition of the server method, not the method on the remote server!    
            return method(*newargs, **newkw) # do the function call
          
        api.__doc__ = fn.__doc__
        setattr( cls, fn.__name__, api )
        return fn
      

# -------------------------------------------------------------------

#
# decorator for methods:
# requires that the class of the method has a method _auth_user_method
# to authorize access to the method
# requires that the method has a parameter 'user' which is a UserCredentials object
#
def _authorized(fn):
    argspec = inspect.getargspec(fn)
    user_index = argspec.args.index( 'user' ) - 1

    def wrapper(server, *args, **kwargs):
      user = args[user_index]      
      if server._auth_user_method( user, fn.__name__ ):
        return fn(server, *args, **kwargs) # do the original function call
      
      return None
    
    return functools.wraps(fn)(wrapper)

# -------------------------------------------------------------------

#
# XMLRPC App
#
class ServerApp : 
  
    def __init__(self, url, config, logginglevel = logging.DEBUG):
        "config is the parameter dictionary; contains server configuration vars"
      
        # get a logger:
        self._logger = logging.getLogger('dirbserver')
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s | %(message)s')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)
        self._logger.setLevel(logginglevel)
        self._logger.info( "Initializing server app" )
        self._url = url
        # ---------------------------------------
        
        # no default shutdown callable -- needs to come from server framework:
        # server really does need to be shutdown cleanly, 
        # to terminate sidecar processes
        # associated with the sandbox.
        self._shutdown_callable = None # needed to shutdown the server above us
        
        
        # ---------------------------------------
        #
        # get configuration settings:
        #
        self._config = conf.get_default_server_config()
        for k in config :
            self._config[k] = copy.deepcopy(config[k])
            
        # ---------------------------------------
        
        self._mutex =  threading.Lock() # TODO: should this be a multi-lock?

        # ---------------------------------------
        
        self._noncecache = {}
        
        
        # ---------------------------------------
        
        self._auth = auth.MethodPermissions( self._config, self._logger )
        
        return
      
    # ===========================================
    
    def _lock(self):
        self._mutex.acquire(True)
        return
        
    def _unlock(self):
        self._mutex.release()
        return    
        
    # ===========================================
        
    def get_nonce( self ):
        nonce = codecs.decode( base64.b64encode(auth.get_nonce()), "utf-8" )
        now = datetime.datetime.now()
        
        self._lock()
        self._noncecache[ nonce ] = now
        self._unlock()
        return nonce
      
    # -------------------------------------------
    
    def _auth_user( self, cred ):
        # prune if past a limit:
        if len( self._noncecache ) > NONCE_CACHE_LIMIT :
            try:
                self._lock()
                keys = self._noncecache.keys() 
                for k in keys:
                    if now - self._noncecache[k] > datetime.timedelta( seconds=NONCE_EXPIRY ) :
                      del self._noncecache[k]
            finally:
                self._unlock()
        
        # need to verify the server nonce before we call auth module to verify the credentials:
        ret = False
        try:
            self._lock()
            timestamp = self._noncecache[ cred.servernonce ]
            if datetime.datetime.now() - timestamp < datetime.timedelta( seconds=NONCE_EXPIRY ):
                del self._noncecache[ cred.servernonce ]
                ret = auth.verify_user_credentials( cred, self._config )
        finally:
            self._unlock()
        if not ret:
            raise SystemError( "Permission Denied" )

        return ret

    # -------------------------------------------
    
    def _auth_user_method( self, user, methodname ):
        # authenticate the user identity first, then whether they can run the method or not
        # encode from generic tuple from the wire to the named tuple we require
        cred = auth.UserCredentials( *user )
        if self._auth_user( cred ): 
            if self._auth.verify( cred.username, methodname ):
                return True

        raise SystemError( "Permission Denied" )
        return False
      
    #############################################
    # ===========================================
    
    # not to be served to clients:
    def set_shutdown_callable(self, fn):
        "Different servers hosting this app need different methods for shutting down"
        self._shutdown_callable = fn

    # ===========================================
    
            
    @_authorized
    @RemoteClient._rpc_all
    def shutdown_server(self, user):
        "friendly shutdown of the cluster"
        cred = auth.UserCredentials( *user )
        self._logger.warning( "Shutdown call received from %s" % cred.username )
        self._lock() # will not release !
        
        return self._shutdown_callable() # execute the callable


    # ===========================================

    @_authorized
    @RemoteClient._rpc_one
    def create_paths(self, createexpr, user, compileddoc, startingpath ):
        "Returns a list of paths that were created from the given creation expression."
        cl = localclient.LocalClient( compileddoc, startingpath ) 
        cred = auth.UserCredentials( *user )
        created = []
        
        # get target paths to create
        target_paths = cl.depict_paths( createexpr )
        
        # sort target paths soas to create shallow directories first
        target_paths = ( (fs.split_path(x.path), x) for x in target_paths )
        target_paths = [ (len(x[0]), x[-1].path, x[-1]) for x in target_paths ]
        target_paths = [ x[-1] for x in sorted( target_paths ) ]
        
        for target in target_paths:
            # acquire permissions, uid, gid
            # TODO: would be nice to cache these credentials to reduce overhead:
            uid = pwd.getpwnam( target.user ).pw_uid if target.user else DEFAULT_UID
            gid = grp.getgrnam( target.group ).gr_gid if target.group else DEFAULT_GID
            permissions = target.permissions if target.permissions else DEFAULT_PERMISSIONS
            
            # create directory
            if not os.path.isdir( target.path ) :
                os.mkdir(target.path)
            
                # set permissions on this directory 
                # will not overwrite existing permissions on existing dirs!
                os.chown(target.path, uid, gid)
                os.chmod(target.path, permissions )
                
                self._logger.debug( "%s created %s" % (cred.username, target.path))
                created.append( target.path )
        
        return created
