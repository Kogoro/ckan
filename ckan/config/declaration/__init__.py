# -*- coding: utf-8 -*-

import logging
from collections import OrderedDict
from typing import Any, Dict, Iterator, List, Set, Union

from ckan.exceptions import CkanConfigurationException

from .key import Key, Pattern
from .option import Option, Annotation, Flag, DefaultType, UNSET, T

from .load import load
from .describe import describe
from .serialize import serialize

log = logging.getLogger(__name__)

__all__ = ["Declaration", "Option", "Annotation", "Flag", "Key"]


class Declaration:
    __slots__ = (
        "_mapping",
        "_order",
        "_plugins",
        "_core_loaded",
        "_sealed",
    )
    _mapping: Dict[Key, Option[Any]]
    _order: List[Union[Key, Annotation, Any]]
    _plugins: Set[str]
    _sealed: bool
    _core_loaded: bool

    def __init__(self):
        self.reset()

    def __bool__(self):
        return bool(self._order)

    def __getitem__(self, key: Key) -> Option[Any]:
        return self._mapping[key]

    def iter_options(
        self,
        *,
        pattern: str = "*",
        exclude: Flag = Flag.ignored | Flag.experimental,
    ) -> Iterator[Key]:
        pat = Pattern.from_string(pattern)
        for k, v in self._mapping.items():
            # if not isinstance(v, Option):
            # continue
            if v._has_flag(exclude):
                continue
            if k != pat:
                continue
            yield k

    def setup(self, config):
        import ckan.plugins as p
        from ckan.common import asbool

        self.reset()
        self.load_core_declaration()
        for plugin in reversed(list(p.PluginImplementations(p.IConfigDeclaration))):
            plugin.declare_config_options(self, Key())
        self.seal()

        if asbool(config.get("config.safe")):
            for key in self.iter_options(exclude=Flag.no_default):
                if key not in config:
                    config[str(key)] = self[key].default

        if asbool(config.get("config.strict")):
            errors = self.validate(config)
            if errors:
                msg = "\n".join(
                    "{}: {}".format(key, "; ".join(issues))
                    for key, issues in errors.items())
                raise CkanConfigurationException(msg)

    def validate(self, config):
        import ckan.lib.navl.dictization_functions as df
        schema = self.into_schema()
        _, errors = df.validate(config.copy(), schema)
        return errors

    def reset(self):
        self._mapping = OrderedDict()
        self._order = []
        self._plugins = set()
        self._core_loaded = False
        self._sealed = False

    def seal(self):
        self._sealed = True

    def load_core_declaration(self):
        if self._core_loaded:
            log.debug("Declaration for core is already loaded")
            return
        self._core_loaded = True
        load(self, "core")

    def load_plugin(self, name: str):
        if name in self._plugins:
            log.debug("Declaration for plugin %s is already loaded", name)
            return
        load(self, "plugin", name)

    def load_dict(self, data: Dict[str, Any]):
        load(self, "dict", data)

    def into_ini(self) -> str:
        return serialize(self, "ini")

    def into_schema(self) -> Dict[str, Any]:
        return serialize(self, "validation_schema")

    def describe(self, fmt: str) -> str:
        return describe(self, fmt)

    def declare(self, key: Key, default: DefaultType[T] = UNSET) -> Option[T]:
        if self._sealed:
            raise TypeError("Sealed declaration cannot be updated")

        value = Option(default)
        if key in self._mapping:
            raise ValueError(f"{key} already declared")
        self._order.append(key)

        self._mapping[key] = value
        return value

    def declare_bool(self, key: Key, default: Any) -> Option[bool]:
        option = self.declare(key, bool(default))
        option.set_validators("boolean_validator")
        return option

    def declare_int(self, key: Key, default: int) -> Option[int]:
        option = self.declare(key, default)
        option.set_validators("convert_int")
        return option

    def annotate(self, annotation: str):
        if self._sealed:
            raise TypeError("Sealed declaration cannot be updated")

        self._order.append(Annotation(annotation))
