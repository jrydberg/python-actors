"""\
Copyright (c) 2009, Donovan Preston.
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import unittest

from pyact import shape


class TestShaped(unittest.TestCase):
    mode = 'static'
    def test_shaped(self):
        self.assertEquals(
            shape.is_shaped("hello", str),
            True)
        self.assertEquals(
            shape.is_shaped(1, int),
            True)
        self.assertEquals(
            shape.is_shaped([1, 2, 3], [int]),
            True)
        self.assertEqual(
            shape.is_shaped(set([8,9]), set([int])),
            True)
        self.assertEqual(
            shape.is_shaped({'a':'b','c':5},
                            {'a':str,'c':int}),
            True)
        self.assertEqual(
            shape.is_shaped((1,'a'),(int,str)),
            True)
        self.assertEqual(
            shape.is_shaped(['x'],set([str])),
            True),
        self.assertEqual(
            shape.is_shaped(['x'],set(['x'])),
            True)
        self.assertEqual(
            shape.is_shaped(set(['x']), [str]),
            True)
        self.assertEqual(
            shape.is_shaped(set(['x']), ['x']),
            True)
                            
                            
        
    def test_not_shaped(self):
        self.assertRaises(
            shape.TypeMismatch,
            shape.is_shaped_exc, 1, str)
        self.assertRaises(
            shape.TypeMismatch, 
            shape.is_shaped_exc, [1, 2, 3], bool)
        self.assertRaises(
            shape.TypeMismatch, 
            shape.is_shaped_exc, {'hello': 'world'}, int)
        self.assertEqual(
            shape.is_shaped(1, bool),
            False)
        self.assertRaises(
            shape.TypeMismatch,
            shape.is_shaped_exc, {'hello': 'world'}, 5)
        self.assertEqual(
            shape.is_shaped(1,2),
            False)
        self.assertEqual(
            shape.is_shaped(str,"z"),
            False)
        self.assertEqual(
            shape.is_shaped(7,['a','b']),
            False)
        self.assertEqual(
            shape.is_shaped((1,2,3),(int,int)),
            False)
        self.assertEqual(
            shape.is_shaped(1,{'a':100}),
            False)
        self.assertEqual(
            shape.is_shaped([1,2,3],(int,int,int)),
            False)
        

    def test_dict_shape(self):
        self.assertEquals(
            shape.is_shaped({'foo': 1}, {'foo': int}),
            True)

    def test_dict_not_shaped(self):
        self.assertRaises(
            shape.KeyMismatch,
            shape.is_shaped_exc, {'bar': 1}, {'foo': int})

    def test_list_shape(self):
        self.assertEquals(
            shape.is_shaped([1, 2, 3], [int]),
            True)

    def test_list_not_shaped(self):
        self.assertRaises(
            shape.TypeMismatch,
            shape.is_shaped_exc, [1, 2], [str])

    def test_tuple_shaped(self):
        self.assertEquals(
            shape.is_shaped(
                (1, "hello", True), (int, str, bool)),
            True)

    def test_tuple_not_shaped(self):
        self.assertRaises(
            shape.SizeMismatch,
            shape.is_shaped_exc,
            (1, "hello", True), (int, str))
        self.assertRaises(
            shape.SizeMismatch,
            shape.is_shaped_exc,
            (1, "hello", True), (int, str, bool, int))

        self.assertRaises(
            shape.TypeMismatch,
            shape.is_shaped_exc,
            (1, "hello", True), (int, str, str))

    def test_deep_nesting(self):
        self.assertEquals(
            shape.is_shaped(
                {'hello': 1, 'world': [{'abc': 'def'}, {'abc': 'def'}]},
                {'hello': int, 'world': [{'abc': str}]}),
            True)

    def test_exact_match(self):
        self.assertEquals(
            shape.is_shaped(
                {'hello': 'world'}, {'hello': 'world'}),
            True)

    def test_exact_mismatch(self):
        self.assertRaises(
            shape.ShapeMismatch, shape.is_shaped_exc,
            {'hello': 'world'}, {'hello': 'something'})


class TestMakeShape(unittest.TestCase):
    mode = 'static'
    def test_simple(self):
        self.assertEquals(shape.calculate_shape(1), int)

    def test_dict(self):
        self.assertEquals(
            shape.calculate_shape({'hello': 'world'}),
            {'hello': str})

    def test_list(self):
        self.assertEquals(
            shape.calculate_shape({'foo': ["one", "two", "three"]}),
            {'foo': [str]})

    def test_tuple(self):
        self.assertEquals(
            shape.calculate_shape({'bar': (1, "hello", True)}),
            {'bar': (int, str, bool)})

    def test_nest(self):
        self.assertEquals(
            shape.calculate_shape(
                {'foo': [{'bar': 1}, {'bar': 2}],
                'baz': ({'bamf': 'hello'}, 5)}),
            {'foo': [{'bar': int}], 'baz': ({'bamf': str}, int)}) 

    def test_malformed(self):
        self.assertRaises(
            shape.AmbiguousShape,
            shape.calculate_shape,
            {'hello': []})
        self.assertRaises(
            shape.HeterogenousList,
            shape.calculate_shape,
            [1, 'hi'])


if __name__ == '__main__':
    unittest.main()

