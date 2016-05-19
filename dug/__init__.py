import functools

import threading


_THREAD_LOCALS = threading.local()


class NotFoundError(KeyError):
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


class _Entry(object):
    __slots__ = [
        'value',
        'dependencies',
        'dependants',
    ]


class Store(object):
    """The core of the DAG, the store is responsible for tracking dependencies
    and caching valuesComponents

    """
    def __init__(self, parent=None):
        self._parent = parent

        self._entries = {}

        # set of targets that have either been replaced, or depend on other
        # targets that have been replaced in the store.
        self._masked = set()

    def cache(self, target, value, dependencies=None):
        if dependencies is None:
            dependencies = set()

        # if any dependencies in self._cache or self._tweaks
        self.invalidate(target)

        entry = _Entry()
        entry.value = value
        entry.dependencies = dependencies
        entry.dependants = set()

        self._entries[target] = entry

        for dependency in dependencies:
            self._entries[dependency].dependants.add(target)

    def __contains__(self, target):
        if target in self._entries:
            return True

        if self._parent is not None and target not in self._masked:
            return target in self._parent

        return False

    def get(self, target, default=None):
        try:
            return self[target]
        except NotFoundError:
            return default

    def __getitem__(self, target):
        if target in self._entries:
            return self._entries[target].value

        if self._parent is not None and target not in self._masked:
            return self._parent[target]

        raise NotFoundError(target)

    def _invalidate_many(self, targets):
        # TODO this can definitely be done better
        if self._parent is not None:
            to_mask = set(targets)

            while to_mask:
                to_mask = set.difference(
                    set.intersection(
                        self._parent.contents(),
                        to_mask
                    ),
                    self._masked
                )
                self._masked = set.union(self._masked, to_mask)

                to_mask = {
                    dependant
                    for target in to_mask
                    for dependant in self._parent.dependants(target)
                }

        to_invalidate = set(targets)

        while to_invalidate:
            to_invalidate = set.intersection(set(self._entries), to_invalidate)
            next_to_invalidate = {
                dependant
                for target in to_invalidate
                for dependant in self._entries[target].dependants
            }

            for target in list(to_invalidate):
                del self._entries[target]
            to_invalidate = next_to_invalidate

    def invalidate(self, target):
        self._invalidate_many({target})

    def contents(self):
        if self._parent is not None:
            set.union(
                set(self._entries),
                set.difference(
                    self._parent.contents(),
                    self._masked,
                )
            )
        else:
            return set(self._entries)

    def dependencies(self, target):
        '''The set of all other targets that a target is known to depend on.
        '''
        if target in self._entries:
            return set(self._entries[target].dependencies)

        if self._parent is not None:
            return self._parent.dependiencies(target)

        return None

    def dependants(self, target):
        '''The set of all other targets that depend on a target.
        '''
        if target in self._entries:
            return set(self._entries[target].dependants)

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
    @property
    def store(self):
        if self._store is None:
            raise OutsideContextError()
        return self._store

    def __init__(self):
        self._store = None
        self._tweaks = {}

    def tweak(self, target, value):
        self._tweaks[target] = value
        return self.store.cache(target, value)

    def cache(self, target, value, dependencies=None):
        self.store.cache(target, value, dependencies=dependencies)

    def get(self, target, default=None):
        return self.store.get(target, default)

    def __getitem__(self, target):
        return self.store[target]

    def __contains__(self, target):
        return target in self.store

    def invalidate(self, target):
        return self.store.invalidate(target)

    def __enter__(self):
        parent = get_storage_context()
        if parent:
            self._store = Store(parent.store)
        else:
            self._store = Store()

        for target, value in self._tweaks.items():
            self.store.cache(target, value)

        push_storage_context(self)
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self._store = None
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
            return storage_context[target]

        with _ExecutionContext() as execution_context:
            result = self.callable(*args)

        storage_context.cache(
            target, result, dependencies=execution_context.dependencies
        )

        return result

    def tweak(self, value, *args):
        storage_context = get_storage_context()
        storage_context.tweak(Target(self, *args), value)


def memoize():
    def _decorator(fn):
        return functools.wraps(fn)(Function(fn))
    return _decorator
