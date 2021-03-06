from inspect import isclass
import six
import sqlalchemy as sa
from sqlalchemy import types
from sqlalchemy_utils import NumericRangeType, IntRangeType
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict


def strip_string(value):
    if isinstance(value, six.string_types):
        return value.strip()
    return value


def is_scalar(value):
    return isinstance(value, (type(None), six.text_type, int, float, bool))


def null_or_unicode(value):
    return six.text_type(value) or None


def null_or_int(value):
    try:
        return int(value)
    except TypeError:
        return None


def flatten(list_):
    result = []
    if isinstance(list_, list):
        for value in list_:
            result.extend(flatten(value))
    else:
        result.append(list_)
    return result


def is_number(type):
    return isinstance(type, types.Integer) or isinstance(type, types.Numeric)


def is_number_range(type):
    return isinstance(type, IntRangeType) or isinstance(type, NumericRangeType)


def is_date_column(column):
    return (
        isinstance(column.type, types.Date) or
        isinstance(column.type, types.DateTime)
    )


def table(model):
    if isinstance(model, sa.schema.Table):
        return model
    else:
        return model.__table__


def primary_keys(model):
    for column in table(model).c:
        if column.primary_key:
            yield column


def find_entity(coll, model, data):
    for column in primary_keys(model):
        if not column.name in data or not data[column.name]:
            return None
        coerce_func = column.type.python_type
        for related_obj in coll:
            value = getattr(related_obj, column.name)

            try:
                if value == coerce_func(data[column.name]):
                    return related_obj
            except ValueError:
                # coerce failed
                pass
    return None


def translated_attributes(model):
    """
    Return translated attributes for current model class. See
    `SQLAlchemy-i18n package`_ for more information about translatable
    attributes.

    .. _`SQLAlchemy-i18n package`:
        https://github.com/kvesteri/sqlalchemy-i18n

    :param model: SQLAlchemy declarative model class
    """
    try:
        translation_class = model.__translatable__['class']
    except AttributeError:
        return []
    return [
        getattr(translation_class, column.key)
        for column in sa.inspect(translation_class).columns
        if not column.primary_key
    ]


def sorted_classes(classes, reverse=False):
    return sorted(
        classes,
        # We need to map classes to ids, since python 3 throws error when
        # trying to compare unorderable types.
        key=lambda a: tuple(id(v) for v in a.__mro__[::-1]),
        reverse=reverse
    )


class ClassMap(OrderedDict):
    """
    An ordered dictionary with keys as classes. ClassMap has the following
    charasteristics:

        1. Checking if a key exists not only matches exact classes but also
        subclasses and objects which are instances of a ClassMap key.

        2. Getting an item of ClassMap with a key matches subclasses and
        instances also.
    """
    def __init__(self, items=None):
        if items:
            items = dict(items)
            sorted_keys = sorted_classes(items.keys(), reverse=True)
            items = [(key, items[key]) for key in sorted_keys]
        else:
            items = {}
        OrderedDict.__init__(self, items)

    def __contains__(self, key):
        """
        Checks if given key exists in by first trying to find an exact match.
        If no exact match is found then this method iterates trhough keys
        and tries to check if given key is either:

            1. A subclass of one of the keys
            2. An instance of one of the keys

        The first check has the time complexity of O(1) whereas the second
        check has O(n).

        Example::



            class A(object):
                pass


            class B(object):
                pass


            class A2(A):
                pass


            class_map = ClassMap({A: 1, B: 2})
            assert B in class_map
            assert A in class_map
            assert A2 in class_map
            assert B() in class_map
            assert A() in class_map
            assert A2() in class_map
        """
        if OrderedDict.__contains__(self, key):
            return True
        test_func = issubclass if isclass(key) else isinstance
        return any(test_func(key, class_) for class_ in self)

    def __getitem__(self, key):
        """
        Returns the item matching a key. The key matching has the same
        charasteristics as __contains__ method.

        Example::

            class A(object):
                pass


            class B(object):
                pass


            class A2(A):
                pass


            class_map = ClassMap({A: 1, B: 2})
            assert class_map[B] == 2
            assert class_map[A] == 1
            assert class_map[A2] == 1
            assert class_map[B()] == 2
            assert class_map[A()] == 1
            assert class_map[A2()] == 1
        """
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            if not isclass(key):
                key = type(key)
            for class_ in self:
                if issubclass(key, class_):
                    return OrderedDict.__getitem__(self, class_)
            raise
