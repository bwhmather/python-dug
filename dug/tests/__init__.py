import unittest

import dug


@dug.memoize()
def _dummy_function(*args):
    pass

_dummy_target = dug.Target(_dummy_function)


class StoreTestCase(unittest.TestCase):
    def test_cache_basic(self):
        store = dug.Store()

        store.cache(_dummy_target, 1)

        self.assertIn(_dummy_target, store)
        self.assertEqual(store[_dummy_target], 1)

    def test_fetch_from_parent(self):
        parent = dug.Store()
        parent.cache(_dummy_target, 'a')

        store = dug.Store(parent=parent)
        self.assertIn(_dummy_target, store)
        self.assertEqual(store[_dummy_target], 'a')

    def test_shadow_value_in_parent(self):
        parent = dug.Store()
        parent.cache(_dummy_target, "parent")

        store = dug.Store(parent=parent)
        store.cache(_dummy_target, "child")
        self.assertIn(_dummy_target, store)
        self.assertEqual(store[_dummy_target], "child"),

    def test_mask_value_in_parent(self):
        parent = dug.Store()
        parent.cache(_dummy_target, "parent")

        store = dug.Store(parent=parent)
        store.invalidate(_dummy_target)

        self.assertNotIn(_dummy_target, store)
        self.assertIsNone(store.get(_dummy_target))


class ContextTestCase(unittest.TestCase):
    def test_basic(self):
        @dug.memoize()
        def dec():
            return 1

        @dug.memoize()
        def bar(x):
            return x - dec()

        @dug.memoize()
        def foo(x):
            return 2 * bar(x)

        self.assertRaises(dug.OutsideContextError, foo, 4)

        with dug.Context() as ctx:
            self.assertEqual(foo(4), 6)
            self.assertEqual(ctx[dug.Target(foo, 4)], 6)

            # change one of the underlying cells
            ctx.tweak(dug.Target(dec), 4)
            self.assertEqual(ctx[dug.Target(dec)], 4)

            # check that everything is invalidated
            self.assertNotIn(dug.Target(foo, 4), ctx)

            self.assertEqual(foo(4), 0)

    def test_tweak_in_nested(self):
        @dug.memoize()
        def node():
            return 'a'

        @dug.memoize()
        def dependant():
            return node() + 'b'

        with dug.Context():
            with dug.Context():
                node.tweak('c')
                self.assertEqual(dependant(), 'cb')

            self.assertEqual(dependant(), 'ab')

    def test_reapply_tweak(self):
        @dug.memoize()
        def node():
            return 'untweaked'

        ctx = dug.Context()
        with ctx:
            node.tweak('tweaked')

        with ctx:
            self.assertEqual(node(), 'tweaked')


loader = unittest.TestLoader()
suite = unittest.TestSuite((
    loader.loadTestsFromTestCase(StoreTestCase),
    loader.loadTestsFromTestCase(ContextTestCase),
))
