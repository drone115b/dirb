#####################################################################
#
# Copyright 2015 SpinVFX 
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
import hashlib
import collections
import threading
import datetime
import stat
import base64
import json
import codecs

try:
    # Assume Linux, OSX:
    import pwd
    import grp
    
    def get_username():
        # getpass.getuser() is too easily forged with environment variables
        return pwd.getpwuid( os.getuid() ).pw_name

    WRITE_CRED_FLAGS = os.O_CREAT | os.O_WRONLY
    
except:
    # windows does not have pwd, grp
    import getpass
    def get_username():
        return getpass.getuser()

    WRITE_CRED_FLAGS = os.O_BINARY | os.O_CREAT | os.O_WRONLY


#
# there exists a directory (confdict['DIRB_AUTHPATH']) which contains two kinds of files:
# (1) user 'password' files, which are named <username>.bin and contain random bytes
#     and whose permissions only allow reading by root or the user, not by anyone else.
#     The contents of the file constitute a shared SECRET with the server running as root.
# (2) a file called _dirb_methods.json (Method permissions file) which contains a nested dictionary:
#    the first key is the name of a server method
#       the value for the method key is a dictionary with keys "groups" or "users"
#       (both keys optional)
#       the values associated the groups or users keys are lists
#       if a username is in the users list for a method
#       or if the username is associated with a group in the groups list for a method
#       then the user will be allowed to run the method.
#       Any method not specified in the file is free for anyone to run.
#
UserCredentials = collections.namedtuple( "UserCredentials", ['username', 'servernonce', 'clientnonce', 'pwhash'])



def _make_userpass_filename ( username, confdict ):
    return os.path.join( confdict['DIRB_AUTHPATH' ], "%s.bin" % username )

def _make_method_permission_filename( confdict ):
    return os.path.join( confdict['DIRB_AUTHPATH' ], '_dirb_methods.json' )
  
def _make_hash( noncehex, clientnonce, filename ) :
   return hashlib.sha256( base64.b64decode(noncehex) + clientnonce + open(filename,'rb').read() ).hexdigest()

def read_method_permissions( confdict ):
    # TODO would be nice if permissions on the filename were proven to be restricted
    filename = _make_method_permission_filename( confdict )
    return json.loads( open( filename, 'rt' ).read() )

def get_nonce():
    "returns a binary, frequently will want to use with base64.b64encode"
    return bytes(os.urandom(32))


def make_user_credentials( username, confdict ):
    "for administrators, though users can probably call themselves too"
    # try to write in a manner that will support windows.
    # Ideally no time between file creation and permissions, so that the
    # file cannot be hijacked on creation.
    filename = _make_userpass_filename( username, confdict )
    try :
        handle =  os.open( filename, WRITE_CRED_FLAGS, stat.S_IRUSR )
        os.write( handle, os.urandom( 512 ) )
        os.close( handle )
        os.chmod( filename, stat.S_IRUSR )
    except:
        if os.path.isfile( filename ):
            os.remove( filename )
        raise

def get_user_credentials( username, confdict, noncehex ):
    "returns UserAuthentication tuple"
    filename = _make_userpass_filename( username, confdict )

    # automatically create a missing authentication file
    # if the username requested is the one running the process
    # or if root owns the current process
    if not os.path.isfile( filename ) :
        # getuid is more secure than getpass.getuser(), which can easily be forged
        # with environment variables
        if get_username() in (username, 'root'):
            make_user_credentials( username, confdict )

    clientnonce = get_nonce()
    dochash = _make_hash( noncehex, clientnonce, filename )
    return UserCredentials( username, noncehex, base64.b64encode(clientnonce).decode('utf-8'), dochash )


def verify_user_credentials( cred, confdict ):
    "This does NOT include the check to verify that the server nonce is valid"
    filename = _make_userpass_filename( cred.username, confdict )
    dochash = _make_hash( cred.servernonce, base64.b64decode(cred.clientnonce), filename)
    return dochash == cred.pwhash


class MethodPermissions ( object ):
    def __init__( self, confdict, logger ) :
        self._authdoc = None
        self._authlock = threading.Lock()
        self._authdate = datetime.datetime.now()
        self._deltatime = datetime.timedelta( seconds=confdict['DIRBSERVER_PERMISSIONS_EXPIRY'] )
        
        self._pwall = {}
        self._grall = None
        self._grname = None
        self._grdate = datetime.datetime.now()
        
        self._conf = confdict
        self._logger = logger

    def verify( self, username, methodname ):
        ret = True
        self._refresh_permdoc()
        try:
            self._authlock.acquire( True )
            usergroups = self._getgroups( username )
            if methodname in self._authdoc :
                ret = False
                if 'groups' in self._authdoc[ methodname ]:
                    ret = any( x in self._authdoc[ methodname ]['groups'] for x in usergroups )
                if not ret and 'users' in self._authdoc[ methodname ]:
                    ret = username in self._authdoc[ methodname ][ 'users' ]
                if not ret:
                    self._logger.error( "Permissions denied to %s, for %s" % (username, methodname))
        finally:
            self._authlock.release()

        return ret

    
    def _refresh_permdoc( self ):
        # read document if time has expired, or if there is no document to start
        # ideally the document has restrictive permissions or the whole thing is moot.
        now = datetime.datetime.now()
        elapsed = now - self._deltatime
        if ( not self._authdoc ) or ( now - self._authdate > self._deltatime ):
            self._authlock.acquire( True )
            self._authdoc = {}
            try:
                self._authdoc = read_method_permissions( self._conf )
            except:
                self._logger.error( "Fail to read method permissions file (%s)" % _make_method_permission_filename( self._conf ))
            finally:
                self._authlock.release()
            self._authdate = now

        
    def _getgroups( self, username ):
        # get all the groups this person of which this person is a member
        # primary group for user:
        
        # performance is dependent upon caching group associations.  Sad face.
        now = datetime.datetime.now()
        if any( not x for x in (self._grname,self._grall,self._pwall)) or ( now - self._grdate > self._deltatime ):
            self._pwall = {} # each key-value loaded on demand
            self._grall = grp.getgrall()
            self._grname = dict(( x.gr_gid, x.gr_name ) for x in self._grall)
            self._grdate = now
        
        if username not in self._pwall :
            self._pwall[ username ] = pwd.getpwnam( username )
        usergroups = [ self._pwall[ username ].pw_gid ]
            
        # secondary groups for user:
        other_groups = [group.gr_gid for group in self._grall if username in group.gr_mem]
        usergroups.extend(other_groups)
            
        # convert from gid to group names
        return set(self._grname[x] for x in usergroups)


    def get_ids( self, username ):
        "returns uid and gid for the given user"
        if username not in self._pwall :
            self._pwall[ username ] = pwd.getpwnam( username )
        return( self._pwall[ username ].pw_uid, self._pwall[ username ].pw_gid )