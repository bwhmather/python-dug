import functools

import threading


_CURRENT_CONTEXT = threading.local()


class NotFoundError(Exception):
    pass


class OutsideContextError(Exception):
    pass


class NoTargetError(Exception):
    pass


def _get_context_stack():
    if not hasattr(_CURRENT_CONTEXT, 'value'):
        _CURRENT_CONTEXT.value = []
    return _CURRENT_CONTEXT.value


def push_context(context):
    stack = _get_context_stack()
    stack.append(context)


def get_context():
    stack = _get_context_stack()
    if not stack:
        raise OutsideContextError()
    return stack[-1]


def pop_context():
    stack = _get_context_stack()
    if not stack:
        raise OutsideContextError()
    return stack.pop()


def _get_target_stack():
    if not hasattr(_THREAD_STATE, 'target_stack'):
        _THREAD_STATE.target_stack = []
    return _THREAD_STATE.target_stack


class Target(object):
    def __init__(self, fn, *args):
        self.function = '%s.%s' % (fn.__module__, fn.__qualname__)
        self.args = tuple(args)

    def __hash__(self):
        return hash((self.function, self.args))

    def __eq__(self, other):
        return (self.function, self.args) == (other.function, other.args)

    def __enter__(self):
        get_context().push_target(self)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        target = get_context().pop_target()
        assert target == self

    def __repr__(self):
        return (
            "<Target %s(" % self.function +
            ", ".join(repr(arg) for arg in self.args) +
            ")>"
        )


def memoize(fn):
    @functools.wraps(fn)
    def call(*args):
        context = get_context()
        target = Target(fn, *args)

        try:
            # register current node as a dependency of the calling node
            context.add_dependencies(target)
        except NoTargetError:
            pass

        try:
            return context.get(target)
        except NotFoundError:
            with target:
                result = fn(*args)
            context.set(target, result)
            return result
    return call


class Context(object):
    def __init__(self, store):
        self.store = store

        self._target_stack = []

    def set(self, target, value):
        self.store.set(target, value)

    def tweak(self, target, value):
        return self.store.tweak(target, value)

    def get(self, target, *args):
        return self.store.get(target, *args)

    def invalidate(self, target):
        return self.store.invalidate(target)

    def add_dependencies(self, *dependencies):
        self.store.add_dependencies(self.get_target(), *dependencies)

    def get_target(self):
        if not len(self._target_stack):
            raise NoTargetError()
        return self._target_stack

    def push_target(self, target):
        self._target_stack.append(target)

    def pop_target(self):
        if not len(self._target_stack):
            raise NoTargetError()
        return self._target_stack.pop()

    def __enter__(self):
        push_context(self)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        context = pop_context()
        assert context == self


class Store():
    def __init__(self, parent=None):
        self._parent = parent

        # map from targets to saved values
        self._store = {}

        # map from targets to the set of targets that they depend on
        self._dependencies = {}

        # map from targets to sets of targets that depend on them
        self._dependants = {}


    def set(self, target, value):
        self.invalidate(target)
        self._store[target] = value

    def tweak(self, target, value):
        raise NotImplementedError()

    def get(self, target, *args):
        if isinstance(target, Target):
            if args:
                raise TypeError("args should be included in target")
        else:
            target = Target(target, *args)

        if target in self._store:
            return self._store[target]
        raise NotFoundError(target, self._store)

    def invalidate(self, target):
        if target in self._store:
            self._store.pop(target)

            # dependants will remove themselves from the set when invalidated
            # so we create a copy to iterate through
            # TODO this means that invalidate might get called on a target
            # multiple times.  Really we should pop
            dependants = list(self._dependants.get(target, set()))

            for dependant in dependants:
                self.invalidate(dependant)

            for dependency in list(self._dependencies.get(target, set())):
                self._dependants[dependency].remove(target)

            # make sure all dependants have been invalidated properly
            assert not self._dependants.get(target)

            # might not exist if target is a root node
            self._dependants.pop(target, None)

            # might not exist if target has no dependencies
            self._dependencies.pop(target, None)

    def add_dependencies(self, target, *dependencies):
        dependencies = set(dependencies)

        self._dependencies.setdefault(target, set()).update(dependencies)

        for dependency in dependencies:
            self._dependants.setdefault(dependency, set()).add(target)
