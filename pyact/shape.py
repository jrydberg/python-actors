"""\
Copyright (c) 2009, Donovan Preston

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

import sys

PY_MAJOR_VERSION = sys.version_info[0]


CONTAINER_TYPES = [dict, list, tuple, set]


class ShapeMismatch(Exception):
    pass


class TypeMismatch(ShapeMismatch):
    pass


class KeyMismatch(ShapeMismatch):
    pass


class SizeMismatch(ShapeMismatch):
    pass


def is_shaped(thing, shape):
    try:
        is_shaped_exc(thing, shape)
        return True
    except ShapeMismatch:
        return False


def is_shaped_exc(thing, shape):
    if PY_MAJOR_VERSION==2:
        #Python 2.x json module will decode str types
        # as unicode. Unicode is actually what JSON spec
        # uses as its 'str' type. 
        #So for Python 2.x cast both things and shapes
        # to unicode first before matching is performed.

        # convert a str(thing) to a unicode(thing)
        if type(thing) == str:
            thing = unicode(thing)

        # convert str(shape) into a unicode(shape)
        if type(shape) == str:
            shape = unicode(shape)
        # if shape _is_ str, use unicode instead
        elif shape == str:
            shape = unicode
            
    shape_type = type(shape)

    if shape_type is object:
        return
    elif shape_type in CONTAINER_TYPES:
        if shape_type is dict:
            if not isinstance(thing, dict):
                raise TypeMismatch("type %s is not a dict" % type(thing))
            for name in shape:
                if name not in thing:
                    raise KeyMismatch(
                        "key %r (for shape %s) was not in dict (%s)" % (
                            name, shape, thing))
                subitem = thing[name]
                subtype = shape[name]
                is_shaped_exc(subitem, subtype)
        elif shape_type in (list, set):
            # use for x in container to work with sets 
            for subtype in shape:
                break
            # subtype is now first element of shape container
            if not isinstance(thing, (list,set)):
                raise TypeMismatch("type %s is not a set or list" % type(thing))
            for subitem in thing:
                is_shaped_exc(subitem, subtype)
        elif shape_type is tuple:
            if not isinstance(thing, tuple):
                raise TypeMismatch("type %s is not a tuple" % type(thing))
            if len(thing) != len(shape):
                raise SizeMismatch(
                    "wrong number of items in %s (for shape %s); "
                    "expected %s items" % (
                    thing, shape, len(shape)))
            subitem_iter = iter(thing)
            for subtype in shape:
                subitem = subitem_iter.next()
                is_shaped_exc(subitem, subtype)
        return
    elif shape_type == type(thing):
        if thing == shape:
            ## It's an exact match
            return
        raise ShapeMismatch("object %r does not match %r" % (thing, shape_type))
    else:
        if isinstance(shape,type) and isinstance(thing,shape):
            ## shape is a basic type and it matches with thing's type
            return 
        raise TypeMismatch("type %r does not match %r (%s)" % (
                thing, shape_type, type(thing)))


class MalformedShape(Exception):
    pass


class AmbiguousShape(MalformedShape):
    pass


class HeterogenousList(MalformedShape):
    pass


def make_pattern(what):
    return str(calculate_shape(what))


def calculate_shape(what):
    what_type = type(what)
    if what_type is dict:
        shape = {}
        for key, value in what.items():
            shape[key] = calculate_shape(value)
        return shape
    elif what_type is list:
        if not len(what):
            raise AmbiguousShape(
                "Shape of item with list of zero elements "
                "cannot be determined")
        subtype = type(what[0])
        for subitem in what[1:]:
            if type(subitem) is not subtype:
                raise HeterogenousList(
                    "List items must be of homogenous type.")
        return [calculate_shape(what[0])]
    elif what_type is tuple:
        return tuple(map(calculate_shape, what))
    else:
        return type(what)

