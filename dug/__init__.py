import functools

import threading


_THREAD_LOCALS = threading.local()


class NotFoundError(Exception):
    pass


class OutsideContextError(Exception):
    pass


class NoTargetError(Exception):
    pass


def _get_storage_context_stack():
    if not hasattr(_THREAD_LOCALS, 'storage_context_stack'):
        _THREAD_LOCALS.storage_context_stack = []
    return _THREAD_LOCALS.storage_context_stack


def push_storage_context(context):
    _get_storage_context_stack().append(context)


def get_storage_context():
    stack = _get_storage_context_stack()
    if not stack:
        return None
    return stack[-1]


def pop_storage_context():
    stack = _get_storage_context_stack()
    if not len(stack):
        raise OutsideContextError()
    return stack.pop()


def _get_execution_context_stack():
    if not hasattr(_THREAD_LOCALS, 'execution_context_stack'):
        _THREAD_LOCALS.execution_context_stack = []
    return _THREAD_LOCALS.execution_context_stack


def push_execution_context(context):
    _get_execution_context_stack().append(context)


def get_execution_context():
    stack = _get_execution_context_stack()
    if not stack:
        return None
    return stack[-1]


def pop_execution_context():
    stack = _get_execution_context_stack()
    if not len(stack):
        raise OutsideContextError()
    return stack.pop()


class Target(object):
    def __init__(self, fn, *args):
        self.function = '%s.%s' % (fn.__module__, fn.__qualname__)
        self.args = tuple(args)

    def __hash__(self):
        return hash((self.function, self.args))

    def __eq__(self, other):
        return (self.function, self.args) == (other.function, other.args)

    def __repr__(self):
        return (
            "<Target %s(" % self.function +
            ", ".join(repr(arg) for arg in self.args) +
            ")>"
        )


class Store(object):
    """The core of the DAG, the store is responsible for tracking dependencies
    and caching valuesComponents

    """
    def __init__(self, parent=None):
        self._parent = parent

        # map from targets to cached values
        self._values = {}

        # set of targets that have been explicitly set in this store and should
        # not be cleared
        self._pinned = set()

        # set of targets that have either been replaced, or depend on other
        # targets that have been replaced in the store.
        self._masked = set()

        # map from targets to the set of targets that they depend on
        self._dependencies = {}

        # map from targets to sets of targets that depend on them
        self._dependants = {}

    def tweak(self, target, value):
        self.cache(target, value)
        self._pinned.add(target)

    def cache(self, target, value, dependencies=None):
        # if any dependencies in self._cache or self._tweaks
        self.invalidate(target)

        self._values[target] = value

        if dependencies is None:
            dependencies = set()

        self._dependencies[target] = dependencies
        for dependency in dependencies:
            self._dependants[dependency].add(target)

        self._dependants[target] = set()

    def __contains__(self, target):
        return target in self._values

    def get(self, target):
        if target in self._values:
            return self._values[target]

        raise NotFoundError(target, self._values)

    def _invalidate_many(self, targets):
        # TODO update mask

        to_invalidate = set(targets)

        while to_invalidate:
            to_invalidate = set.intersection(set(self._values), to_invalidate)
            next_to_invalidate = {
                dependant
                for target in to_invalidate
                for dependant in self._dependants[target]
            }

            for target in list(to_invalidate):
                del self._values[target]
                del self._dependencies[target]
                del self._dependants[target]
            to_invalidate = next_to_invalidate

    def invalidate(self, target):
        self._invalidate_many({target})

    def add_dependencies(self, target, *dependencies):
        dependencies = set(dependencies)

        self._dependencies.setdefault(target, set()).update(dependencies)

        for dependency in dependencies:
            self._dependants.setdefault(dependency, set()).add(target)

    def contents(self, target):
        if self._parent is not None:
            frozenset.union(
                frozenset(self._values),
                frozenset.difference(
                    self._parent.contents(),
                    self._masked,
                )
            )
        else:
            return frozenset(self._values)

    def dependencies(self, target):
        '''The set of all other targets that a target is known to depend on.
        '''
        if target in self._dependencies:
            return frozenset(self._dependencies[target])

        if self._parent is not None:
            return self._parent.dependiencies(target)

        return None

    def dependants(self, target):
        '''The set of all other targets that depend on a target.
        '''
        if target in self._dependants:
            return frozenset(self._dependants[target])

        if self._parent is not None:
            return self._parent.dependants(target)

        return None


class _ExecutionContext(object):
    def __init__(self):
        self.dependencies = set()

    def add_dependency(self, dependency):
        self.dependencies.add(dependency)

    def __enter__(self):
        push_execution_context(self)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pop_execution_context()


class Context(object):
    def tweak(self, target, value):
        return self.store.tweak(target, value)

    def cache(self, target, value, dependencies=None):
        self.store.cache(target, value, dependencies=dependencies)

    def get(self, target):
        return self.store.get(target)

    def __contains__(self, target):
        return target in self.store

    def invalidate(self, target):
        return self.store.invalidate(target)

    def __enter__(self):
        parent = get_storage_context()
        if parent:
            self.store = Store(parent.store)
        else:
            self.store = Store()

        push_storage_context(self)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.store = None
        pop_storage_context()


class Function(object):
    def __init__(self, callable):
        self.callable = callable

    def __call__(self, *args):
        # The storage context isn't needed until later but it's better to check
        # up front that it exists
        storage_context = get_storage_context()
        if storage_context is None:
            raise OutsideContextError()

        # Same with creating the target.  We need to make sure that all of the
        # arguments are suitable.
        target = Target(self, *args)

        # If evaluated by another dug function we should register this target
        # as a dependency.
        parent_execution_context = get_execution_context()
        if parent_execution_context is not None:
            parent_execution_context.add_dependency(target)

        # Try to load result from cache.
        if target in storage_context:
            return storage_context.get(target)

        with _ExecutionContext() as execution_context:
            result = self.callable(*args)

        storage_context.cache(
            target, result, dependencies=execution_context.dependencies
        )

        return result


def memoize():
    def _decorator(fn):
        return functools.wraps(fn)(Function(fn))
    return _decorator
