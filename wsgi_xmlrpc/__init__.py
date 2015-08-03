#   Copyright (c) 2006-2007 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.



try: # python 3.2 compatibility, Mayur Patel, mpatel@spinpro.com Aug 14
    import xmlrpc.server as xmlrpc_server
    def b(val):
        """ Convert string/unicode/bytes literals into bytes.  This allows for
        the same code to run on Python 2.x and 3.x. """
        if isinstance(val, str):
            return val.encode()
        else:
            return val

    def u(val, encoding="us-ascii"):
        """ Convert bytes into string/unicode.  This allows for the
        same code to run on Python 2.x and 3.x. """
        if isinstance(val, bytes):
            return val.decode(encoding)
        else:
            return val
except:
    import SimpleXMLRPCServer as xmlrpc_server
    def b(val):
        """ Convert string/unicode/bytes literals into bytes.  This allows for
        the same code to run on Python 2.x and 3.x. """
        if isinstance(val, unicode):
            return val.encode()
        else:
            return val

    def u(val, encoding="us-ascii"):
        """ Convert bytes into string/unicode.  This allows for the
        same code to run on Python 2.x and 3.x. """
        if isinstance(val, str):
            return val.decode(encoding)
        else:
            return val

import logging
import traceback

logger = logging.getLogger(__name__)

class WSGIXMLRPCApplication(object):
    """Application to handle requests to the XMLRPC service"""

    def __init__(self, instance=None, methods=[], do_log=True):
        """Create windmill xmlrpc dispatcher"""
        try:
            self.dispatcher = xmlrpc_server.SimpleXMLRPCDispatcher(allow_none=True, encoding=None)
        except TypeError:
            # python 2.4
            self.dispatcher = xmlrpc_server.SimpleXMLRPCDispatcher()
        if instance is not None:
            self.dispatcher.register_instance(instance)
        for method in methods:
            self.dispatcher.register_function(method)
        self.dispatcher.register_introspection_functions()

    def handler(self, environ, start_response):
        """XMLRPC service for windmill browser core to communicate with"""

        if environ['REQUEST_METHOD'] == 'POST':
            return self.handle_POST(environ, start_response)
        else:
            start_response("400 Bad request", [('Content-Type','text/plain')])
            return ['']
        
    def handle_POST(self, environ, start_response):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the server's _dispatch method for handling.
        
        Most code taken from SimpleXMLRPCServer with modifications for wsgi and my custom dispatcher.
        """
        
        try:
            # Get arguments by reading body of request.
            # We read this in chunks to avoid straining
            # socket.read(); around the 10 or 15Mb mark, some platforms
            # begin to have problems (bug #792570).

            length = int(environ['CONTENT_LENGTH'])
            data = environ['wsgi.input'].read(length)
            
            max_chunk_size = 10*1024*1024
            size_remaining = length

            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and 
            # using that method if present.
            response = self.dispatcher._marshaled_dispatch(
                    data, getattr(self.dispatcher, '_dispatch', None)
                )
            response += b('\n')
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            start_response("500 Server error", [('Content-Type', 'text/plain')])
            logger.warn('500 %s:\n%s' % (environ['REMOTE_ADDR'], traceback.format_exc()))
            return []
        else:
            # got a valid XML RPC response
            start_response("200 OK", [('Content-Type','text/xml'), ('Content-Length', str(len(response)),)])
            logger.info('200 %s' % environ['REMOTE_ADDR'])
            return [response]
            

    def __call__(self, environ, start_response):
        return self.handler(environ, start_response)
