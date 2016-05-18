Python DUG
==========

|build-status| |coverage|



Calculating a node
  - if a trace context exists add head to list of deps
  - if a value exists for this set of args, return it
  - otherwise
      - push self onto trace context stack
      - execute as normal
      - save value and args
      - return


Setting a node




evaluation:
  - if a trace context is set, bind the caller as a dependency
  - if result already in db just return that
  - setup trace env
  - evaluate function


setting a node
  - start a transaction
  - change the node
  - invalidate all dependencies/notify all listeners
  - clobber





persistance:
  - dag object path
  - dag method name
  - list of argument values


Components
----------
Cache:
  - Created on entering a context
  - Populated with tweaks from the owning context
  - No support for rebuilding on top of a parent cache, must be recreated from tweaks stored in the context.
  - Should not forward changes on to parent cache.  Nodes in parent cache that have different values from what they would in the child cache should be marked as masked.





Identifying nodes
-----------------

Node identifiers must be serializable.
It probably makes sense for node identifiers to just hold a reference to the function and rely on pickle or whatever to deal with the wire format.


Stacked contexts, tweaking, and cache invalidation
--------------------------------------------------

The rules:
Tweaked nodes are masked.
Nodes depending on masked nodes are also masked.
Nodes marked as masked should not be fetched from the parent context.
The results of nodes marked as masked should be stored in the current context's cache.
Nodes can be marked as masked and stored in the cache.
Nodes can be marked as masked and not stored in the cache.


Tweaking a node:

When tweaking a node it is necessary to mark all of its descendants as masked.
This can be done recursively.
On encountering a node that is already marked as masked, it can be assumed that all of its descendants are also marked as masked.  This means that it is not necessary to recurse past it.


Re-entering a context:

It is possible that on re-entering a context, the parent context will have changed.  It will probably always be necessary to re-tweak all nodes in the context.

Some part of the cache will have to be invalidated to account for changes in the new parent.
It might be possible to invalidate only the parts marked masked in the parent context.
It might make sense to always clear the cache on exiting the context no matter what.  This would allow contexts to be used as a way to avoid excessive caching.


Garbage collection
------------------

It has been suggested that garbage collection is probably not actually necessary.  Instead rely on discarding contexts to get granular control over what stuff to keep.



Questions
---------

  - Is there a way to split tweaking from caching?




.. |build-status| image:: https://travis-ci.org/bwhmather/python-dug.png?branch=develop
    :target: https://travis-ci.org/bwhmather/python-dug
    :alt: Build Status
.. |coverage| image:: https://coveralls.io/repos/bwhmather/python-dug/badge.png?branch=develop
    :target: https://coveralls.io/r/bwhmather/python-dug?branch=develop
    :alt: Coverage
.. _warner/python-dug: https://github.com/warner/python-dug
