"""按声明顺序读取不可变数值记录，省去对float/int的递归深拷贝。"""

from dataclasses import fields
from functools import lru_cache
from operator import attrgetter


@lru_cache(maxsize=None)
def _reader(record_type):
    return attrgetter(*(field.name for field in fields(record_type)))


def scalar_values(record):
    """仅用于本工程字段均为数值的冻结dataclass记录。"""
    return _reader(type(record))(record)
