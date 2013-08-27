# python-actors

This is some work on Donovan Preston's python-actors [1] so that it
works with gevent.

Since the dawn of concurrency research, there have been two camps:
shared everything, and shared nothing. Most modern applications use
threads for concurrency, a shared everything architecture.

Actors, however, use a shared nothing architecture where lightweight
processes communicate with each other using message passing. Actors
can change their state, create a new Actor, send a message to any
Actor it has the Address of, and wait for a specific kind of message
to arrive in it's mailbox.

[1] https://bitbucket.org/fzzzy/python-actors

Requirements:

 * gevent 0.13
 * simplejson
 * a large dose of patience

# What Is an Actor?

* An actor is a process
* An actor can change it's own state
* An actor can create another actor and get it's address
* An actor can send a message to any addresses it knows
* An actor can wait for a specific message to arrive in it's mailbox

# Why Use Actors?

* Only an actor can change it's own state
* Each actor is a process, simplifying control flow
* Message passing is easy to distribute
* Most exceptional conditions occur when waiting for a message
* Isolates error handling code
* Makes it easier to build fault tolerant distributed systems

# How Are Actors Implemented in python-actors?

*gevent* and greenlet threads are used to implement the actor
processes.  This doesn't provide real isolation: but python doesn't
provide private either.

When messages are sent between actors they are serialized to json and
copied.  This provides isolation and makes the messages network safe.

Problem: Imported modules leak state between actors

* Possibility: Keep a unique copy of sys.modules for every actor
* Possibility: Seal modules in wrapper object preventing modification
* Reality: Just write code that doesn't abuse global module state

# How To Use python-actors

Most stuff lives in the `pyact` package and in the `actor` module:

 * `pyact.actor.Actor` is an actor.

Create an actor.

    from pyact import actor
    address = actor.spawn(fn)

`fn` is a function that receives a *receive* funcion as the first
argument.

There are two ways to create an actor: either by subclassing `Actor`
or by just passing a function to `spawn`.  Arguments passed to `spawn`
are forwarded to the actor:

    def forward(receive, address):
        pat, data = receive()
        address | data

    def build(receive, n):
        ring = []
        for i in range(n):
            if not ring:
                node = actor.spawn(forward, actor.curaddr())
            else:
                node = actor.spawn(forward, ring[-1])
            ring.append(node)
            gevent.sleep()

        ring[-1] | {'text': 'hello around the ring'}
        pat, data = receive()
        return data

    addr = actor.spawn(build, 10000)
    print addr.wait()

This passes *10000* as `n` to the actor function `build`.  This
creates 10,000 sub-actors, where actor N will forward any received
message to actor N+1 and then die.  When all actors has been created a
message is sent through the ring.

Worth noting is the `curaddr()` function that returns the address of
the current actor.  Another neat function is the `node.wait` function
that waits for a local actor to finish and returns the result.

## Receiving Messages

`python-actors` has just like Erlang selective receive.  This means
that if messages in the mailbox will be left there if the call to
*receive* do not provide a matching pattern.

Patterns are python objects that can contain "wildcard types".  A
simple example is the following dictionary pattern: `{"name": int}`.
This will match `{"name": 1}` but not `{"name": "data"}`.  The type
`object` will match anything.

    DATA = ('data', str)
    EVENT = {'event': str, 'data': object}

    pat, msg = receive(DATA, EVENT)
    if pat is DATA:
       print "we got some data", msg[1]
    if pat is EVENT:
       print "wow, an event", msg['event'], msg['data']

Note that tuples must match is length.  This is not true for lists,
which is used to match arrays.  The first element in an array match is
a type: `[str]` will match `['a', 'b']` but not `[1, 'b']`.

# Roadmap

* Proper linking and monitoring
* Create basic constructs such as supervisors and routers
