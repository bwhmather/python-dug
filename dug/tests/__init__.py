import unittest

import dug


class DugTestCase(unittest.TestCase):
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
            self.assertEqual(ctx.get(dug.Target(foo, 4)), 6)

            # change one of the underlying cells
            ctx.tweak(dug.Target(dec), 4)
            self.assertEqual(ctx.get(dug.Target(dec)), 4)

            # check that everything is invalidated
            self.assertRaises(dug.NotFoundError, ctx.get, dug.Target(foo, 4))

            self.assertEqual(foo(4), 0)


loader = unittest.TestLoader()
suite = unittest.TestSuite((
    loader.loadTestsFromTestCase(DugTestCase),
))
