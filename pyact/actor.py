# Copyright (c) 2013 Johan Rydberg
# Copyright (c) 2009 Donovan Preston
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys
import traceback
import urlparse
import uuid
import weakref
import base64


try:
    import simplejson as json
except ImportError:
    import json

from gevent import event
import gevent

#import eventlet
#from eventlet import hubs
#from eventlet import event
#from eventlet import greenlet

#from eventlet.green import httplib

from pyact import exc
from pyact import shape


## If set to true, an Actor will print out every exception, even if the parent
## handles the exception properly.
NOISY_ACTORS = False


class ActorError(RuntimeError):
    """Base class for actor exceptions.
    """


class Killed(ActorError):
    """Exception which is raised when an Actor is killed.
    """
    pass


class DeadActor(ActorError):    
    """Exception which is raised when a message is sent to an Address which
    refers to an Actor which is no longer running.
    """
    pass

class ReceiveTimeout(ActorError):
    """Internal exception used to signal receive timeouts.
    """
    pass

class RemoteAttributeError(ActorError, AttributeError):
    pass


class RemoteException(ActorError):
    pass

class InvalidCallMessage(ActorError):
    """Message doesn't match call message shape.
    """
    pass

def is_actor_type(obj):
    """Return True if obj is a subclass of Actor, False if not.
    """
    try:
        return issubclass(obj, Actor)
    except TypeError:
        return False


def spawn(spawnable, *args, **kw):
    """Start a new Actor. If spawnable is a subclass of Actor,
    instantiate it with no arguments and call the Actor's "main"
    method with *args and **kw.

    If spawnable is a callable, call it inside a new Actor with the first
    argument being the "receive" method to use to retrieve messages out
    of the Actor's mailbox,  followed by the given *args and **kw.

    Return the Address of the new Actor.
    """
    if is_actor_type(spawnable):
        spawnable = spawnable()
    else:
        spawnable = Actor(spawnable)

    spawnable._args = (args, kw)
    gevent.spawn_later(0, spawnable.switch)
    return spawnable.address


def spawn_link(spawnable, *args, **kw):
    """Just like spawn, but call actor.add_link(gevent.getcurrent().address)
    before returning the newly-created actor.

    The currently running Actor will be linked to the new actor. If an
    exception occurs or the Actor finishes execution, a message will
    be sent to the Actor which called spawn_link with details.

    When an exception occurs, the message will have a pattern like:

        {'address': gevent.actor.Address, 'exception': dict}

    The "exception" dict will have information from the stack trace extracted
    into a tree of simple Python objects.

    On a normal return from the Actor, the actor's return value is given
    in a message like:

        {'address': gevent.actor.Address, 'exit': object}
    """
    if is_actor_type(spawnable):
        spawnable = spawnable()
    else:
        spawnable = Actor(spawnable)

    spawnable._args = (args, kw)
    spawnable.add_link(gevent.getcurrent().address)
    gevent.spawn_later(0, spawnable.switch)
    return spawnable.address


def handle_custom(obj):
    if isinstance(obj, Address) or isinstance(obj,Binary):
        return obj.to_json()
    raise TypeError(obj)

def generate_custom(obj):
    address = Address.from_json(obj)
    if address: 
        return address
    binary = Binary.from_json(obj)
    if binary:
        return binary
    return obj

class Binary(object):
    """A custom Binary object. Wrap binaries in this class before
    sending them inside messages.
    """
    def __init__(self,value):
        self.value=value

    def to_json(self):
        return {'_pyact_binary':base64.b64encode(self.value)}
    
    @classmethod
    def from_json(cls,obj):
        if obj.keys() == ['_pyact_binary']:
            return cls(base64.b64decode(obj['_pyact_binary']))
        return None
    
    def __hash__(self):
        return hash(self.value)
    
    def __eq__(self,o):
        if isinstance(o,Binary):
            return self.value == o.value
        return self.value == o

    def __repr__(self):
        return 'Binary('+self.value+')'

    def __str__(self):
        return repr(self)

    
class Address(object):
    """An Address is a reference to another Actor.  Any Actor which has an
    Address can asynchronously put a message in that Actor's mailbox. This is
    called a "cast". To send a message to another Actor and wait for a response,
    use "call" instead.
    """
    def __init__(self, actor):
        self.__actor = weakref.ref(actor)

    def to_json(self):
        return {'_pyact_address':self.actor_id}
    
    @classmethod
    def from_json(cls,obj):
        if obj.keys() == ['_pyact_address']:
            return Actor.all_actors[obj['_pyact_address']].address
        return None

    @staticmethod
    def lookup(name):
        """Return the Address of an Actor given the actor_id as a string.
        """
        return Actor.all_actors[name].address

    @property
    def _actor(self):
        """This will be inaccessible to Python code in the C implementation.
        """
        actor = self.__actor()
        if actor is None or actor.dead:
            raise DeadActor()
        return actor

    @property
    def actor_id(self):
        return self._actor.actor_id

    def link(self, trap_exit=True):
        """Link the current Actor to the Actor at this address. If the linked
        Actor has an exception or exits, a message will be cast to the current
        Actor containing details about the exception or return result.
        """
        self._actor.add_link(gevent.getcurrent().address, trap_exit=trap_exit)

    def cast(self, message):
        """Send a message to the Actor this object addresses.
        """
        ## If messages are any Python objects (not necessarily dicts), 
        ## but they specify the _as_json_obj() method, that method 
        ## will be called to get  json object representation of that
        ## object.
        if hasattr(message,'_as_json_obj'):
            message = message._as_json_obj()
        self._actor._cast(json.dumps(message, default=handle_custom))

    def __or__(self, message):
        """Use Erlang-y syntax (| instead of !) to send messages.
               addr | msg  
        is equivalent to:
               addr.cast(msg)
        """
        self.cast(message)

    def call(self, method, message=None, timeout=None):
        """Send a message to the Actor this object addresses.
        Wait for a result. If a timeout in seconds is passed, raise
        gevent.TimeoutError if no result is returned in less than the timeout.
        
        This could have nicer syntax somehow to make it look like an actual method call.
        """
        message_id = str(uuid.uuid1())
        my_address = gevent.getcurrent().address
        self.cast(
                {'call': message_id, 'method': method,
                'address': my_address, 'message': message})
        if timeout is None:
            cancel = None
        else:
            ## Raise any Timeout to the caller so they can handle it
            cancel = gevent.Timeout(timeout)
            cancel.start()

        RSP = {'response': message_id, 'message': object}
        EXC = {'response': message_id, 'exception': object}
        INV = {'response': message_id, 'invalid_method': str}

        pattern, response = gevent.getcurrent().receive(RSP, EXC, INV)

        if cancel is not None:
            cancel.cancel()

        if pattern is INV:
            raise RemoteAttributeError(method)
        elif pattern is EXC:
            raise RemoteException(response)
        return response['message']

    def __getattr__(self,method):
        """Support address.<method>(message,timout) call pattern.

        For example:
              addr.call('test') could be written as addr.test()
              
        """
        f = lambda message=None,timeout=None : self.call(method,message,timeout)
        return f
        
    def wait(self):
        """Wait for the Actor at this Address to finish, and return it's result.
        """
        return self._actor._exit_event.get()

    def kill(self):
        """Violently kill the Actor at this Address. Any other Actor which has
        called wait on this Address will get a Killed exception.
        """
        gevent.kill(self._actor, Killed)


CALL_PATTERN = {'call': str, 
                'method': str, 
                'address': Address, 
                'message': object}
REMOTE_CALL_PATTERN = {'remotecall':str,
                       'method':str,
                       'message':object,
                       'timeout':object}
RESPONSE_PATTERN = {'response': str, 'message': object}
INVALID_METHOD_PATTERN = {'response': str, 'invalid_method': str}
EXCEPTION_PATTERN = {'response': str, 'exception':object}

def build_call_pattern(method,message=object):
    call_pat = CALL_PATTERN.copy()
    call_pat['method'] = method
    call_pat['message'] = message
    return call_pat

def lazy_property(property_name, property_factory, doc=None):
    def get(self):
        if not hasattr(self, property_name):
            setattr(self, property_name, property_factory(self))
        return getattr(self, property_name)
    return property(get)


class Actor(gevent.Greenlet):
    """An Actor is a Greenlet which has a mailbox.  Any other Actor
    which has the Address can asynchronously put messages in this
    mailbox.

    The Actor extracts messages from this mailbox using a technique
    called selective receive. To receive a message, the Actor calls
    self.receive, passing in any number of "shapes" to match against
    messages in the mailbox.
    
    A shape describes which messages will be extracted from the
    mailbox.  For example, if the message ('credit', 250.0) is in the
    mailbox, it could be extracted by calling self.receive(('credit',
    int)). Shapes are Python object graphs containing only simple
    Python types such as tuple, list, dictionary, integer, and string,
    or type object constants for these types.
    
    Since multiple patterns may be passed to receive, the return value
    is (matched_pattern, message). To receive any message which is in
    the mailbox, simply call receive with no patterns.
    """
    _wevent = None
    _mailbox = lazy_property('_p_mailbox', lambda self: [])
    _alinks = lazy_property('_p_links', lambda self: [])
    _exit_links = lazy_property('_p_exit_links', lambda self: [])
    _exit_event = lazy_property('_p_exit_event', lambda self: event.AsyncResult())

    address = lazy_property('_p_address', lambda self: Address(self),
        doc="""An Address is a reference to another Actor. See the Address
        documentation for details. The address property is the Address
        of this Actor.
        """)

    spawn = classmethod(spawn)
    spawn_link = classmethod(spawn_link)

    all_actors = {}

    actor_id = property(lambda self: self._actor_id)

    def __init__(self, run=None):
        if run is None:
            self._to_run = self.main
        else:
            self._to_run = lambda *args, **kw: run(self.receive, *args, **kw)
        gevent.Greenlet.__init__(self)

        self._actor_id = str(uuid.uuid1())
        self.all_actors[self.actor_id] = self

    #######
    ## Methods for general use
    #######

    def rename(self, name):
        """Change this actor's public name on this server.
        """
        del self.all_actors[self.actor_id]
        self._actor_id = name
        self.all_actors[name] = self

        
    def _match_patterns(self,patterns):
        """Internal method to match a list of patterns against
        the mailbox. If message matches any of the patterns,
        that message is removed from the mailbox and returned
        along with the pattern it matched. If message doesn't
        match any pattern then None,None is returned.
        """
        for i, message in enumerate(self._mailbox):
            for pattern in patterns:
                if shape.is_shaped(message, pattern):
                    del self._mailbox[i]
                    return pattern, message
        return None,None
        
    def receive(self, *patterns, **kw):
        """Select a message out of this Actor's mailbox. If patterns
        are given, only select messages which match these shapes.
        Otherwise, select the next message.
        """
        timeout = kw.get('timeout',None)
        if timeout == 0 :
            if not patterns:
                if self._mailbox:
                    return {object: object}, self._mailbox.pop(0)
                else:
                    return None,None
            return self._match_patterns(patterns)
        if timeout is not None:
            timer = gevent.Timeout(kw['timeout'], ReceiveTimeout)
            timer.start()
        else:
            timer = None
        try:
            while True:
                if patterns:
                    matched_pat, matched_msg = self._match_patterns(patterns)
                elif self._mailbox:
                    matched_pat, matched_msg = {object:object},self._mailbox.pop(0)
                else:
                    matched_pat = None
                if matched_pat is not None:
                    if timer:
                        timer.cancel()
                    return matched_pat,matched_msg
                self._wevent = event.Event()
                try:
                    # wait until at least one message or timeout
                    self._wevent.wait()
                finally:
                    self._wevent = None
        except ReceiveTimeout:
            return (None,None)
        #except gevent.Timeout, t:
        #    if t is not timer:
        #        raise
        #    return (None,None)


    def respond(self, orig_message, response=None):
        if not shape.is_shaped(orig_message, CALL_PATTERN):
            raise InvalidCallMessage(str(orig_message))
        orig_message['address'].cast({'response':orig_message['call'],
                                      'message':response})

    def respond_invalid_method(self, orig_message, method):
        if not shape.is_shaped(orig_message, CALL_PATTERN):
            raise InvalidCallMessage(str(orig_message))
        orig_message['address'].cast({'response':orig_message['call'],
                                      'invalid_method':method})

    def respond_exception(self, orig_message, exception):
        if not shape.is_shaped(orig_message, CALL_PATTERN):
            raise InvalidCallMessage(str(orig_message))
        orig_message['address'].cast({'response':orig_message['call'],
                                      'exception':exception})
    def add_link(self, address, trap_exit=True):
        """Link the Actor at the given Address to this Actor.

        If this Actor has an unhandled exception, cast a message containing details
        about the exception to the Address. If trap_exit is True, also cast a message
        containing the Actor's return value when the Actor exits.
        """
        assert isinstance(address, Address)
        self._alinks.append(address)
        if trap_exit:
            self._exit_links.append(address)

    def main(self, *args, **kw):
        """If subclassing Actor, override this method to implement the Actor's
        main loop.
        """
        raise NotImplementedError("Implement in subclass.")

    def cooperate(self):
        self.sleep(0)

    def sleep(self, amount):
        gevent.sleep(amount)

    #######
    ## Implementation details
    #######

    def _run(self):
        """Do not override.

        Run the Actor's main method in this greenlet. Send the function's
        result to the Actor's exit event. Also, catch exceptions and send
        messages with the exception details to any linked Actors, and send
        an exit message to any linked Actors after main has completed.
        """
        args, kw = self._args
        del self._args
        to_run = self._to_run
        del self._to_run
        try:
            result = to_run(*args, **kw)
            self._exit_event.set(result)
        except:
            exctype, excvalue, excinfo = sys.exc_info()
            if NOISY_ACTORS:
                print "Actor had an exception:"
                traceback.print_exc()
            result = None
            formatted = exc.format_exc()
            for link in self._alinks:
                link.cast({'address': self.address, 'exception': formatted})
            self._exit_event.set_exception(excvalue)
        for link in self._exit_links:
            link.cast({'address': self.address, 'exit': result})
        self.all_actors.pop(self.actor_id)

    def _cast(self, message, as_json=True):
        """For internal use.
        
        Address uses this to insert a message into this Actor's mailbox.
        """
        if as_json:
            message = json.loads(message, object_hook=generate_custom)
        self._mailbox.append(message)
        if self._wevent and not self._wevent.is_set():
            self._wevent.set()


class Server(Actor):
    """An actor which responds to the call protocol by looking for the
    specified method and calling it.

    Also, Server provides start and stop methods which can be overridden
    to customize setup.
    """
    def server_start(self, *args, **kw):
        """Override to be notified when the server starts.
        """
        pass

    def server_stop(self, *args, **kw):
        """Override to be notified when the server stops.
        """
        pass

    def main(self, *args, **kw):
        """Implement the actor main loop by waiting forever for messages.
        
        Do not override.
        """
        self.server_start(*args, **kw)
        try:
            while True:
                pattern, message = self.receive(CALL_PATTERN)
                method = getattr(self, message['method'], None)
                if method is None:
                    self.respond_invalid_method(message, message['method'])
                    continue
                try:
                    self.respond(message, method(message['message']))
                except Exception, e:
                    formatted = exc.format_exc()
                    self.respond_exception(message, formatted)
        finally:
            self.server_stop(*args, **kw)


class Gather(Actor):

    def main(self, spawnable_list):
        address_list = [spawn_link(x) for x in spawnable_list]

        messages = {}
        current_index = 0
        results = []
        for i in range(len(address_list)):
            _pattern, message = self.receive(
                {'exit': object, 'address': object},
                {'exception': object, 'address': object})

            messages[message['address']] = message
            if address_list[current_index] in messages:
                results.append(messages[address_list[current_index]])
                current_index += 1
        return results


def wait_all(*spawnable_list):
    if len(spawnable_list) == 1 and isinstance(spawnable_list[0], list):
        spawnable_list = spawnable_list[0]
    return spawn(Gather, spawnable_list).wait()

