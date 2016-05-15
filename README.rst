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









.. |build-status| image:: https://travis-ci.org/bwhmather/python-dug.png?branch=develop
    :target: https://travis-ci.org/bwhmather/python-dug
    :alt: Build Status
.. |coverage| image:: https://coveralls.io/repos/bwhmather/python-dug/badge.png?branch=develop
    :target: https://coveralls.io/r/bwhmather/python-dug?branch=develop
    :alt: Coverage
.. _warner/python-dug: https://github.com/warner/python-dug
