# -*- mode: python; tab-width: 4; indent-tabs-mode: t; python-indent-offset: 4; coding: utf-8 -*-
from typing import TypeVar, Type, Generic, Sequence, Callable, Tuple, ClassVar
import struct, enum, math
from abc import abstractmethod
_MESSAGE_MAGIC = 0xB5C0C4B3
_TEXT_MAGIC = 0xD812C8F5
_BYTES_MAGIC = 0xDCDBBE10
_LIST_MAGIC = 0x3400BB46
