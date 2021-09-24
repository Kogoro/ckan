# -*- coding: utf-8 -*-

import abc
from io import StringIO
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from .key import Key
from .option import Option, Flag, Annotation
from .utils import FormatHandler

if TYPE_CHECKING:
    from . import Declaration

EXCLUDE = Flag.internal | Flag.ignored | Flag.experimental

handler: FormatHandler[Callable[["Declaration", Flag], str]] = FormatHandler()
describe = handler.handle


@handler.register("toml")
def describe_toml(declaration: "Declaration", exclude: Flag = EXCLUDE):
    describer = TomlDescriber()
    return describer(declaration, exclude)


@handler.register("json")
def describe_json(declaration: "Declaration", exclude: Flag = EXCLUDE):
    describer = JsonDescriber()
    return describer(declaration, exclude)


@handler.register("yaml")
def describe_yaml(declaration: "Declaration", exclude: Flag = EXCLUDE):
    describer = YamlDescriber()
    return describer(declaration, exclude)


@handler.register("python")
def describe_python(declaration: "Declaration", exclude: Flag = EXCLUDE):
    describer = PythonDescriber()
    return describer(declaration, exclude)


@handler.register("dict")
def describe_dict(declaration: "Declaration", exclude: Flag = EXCLUDE):
    describer = DictDescriber()
    return describer(declaration, exclude)


class AbstractDescriber(metaclass=abc.ABCMeta):
    __slots__ = ()

    def __call__(
        self,
        declaration: "Declaration",
        exclude: Flag,
    ):
        for item in declaration._order:
            if isinstance(item, Annotation):
                self.annotate(item)
            elif isinstance(item, Key):
                option = declaration._mapping[item]
                if option._has_flag(exclude):
                    continue
                self.add_option(item, option)
        return self.finalize()

    @abc.abstractmethod
    def add_option(self, key: Key, option: Option) -> None:
        pass

    @abc.abstractmethod
    def annotate(self, annotation: str) -> None:
        pass

    @abc.abstractmethod
    def finalize(self) -> str:
        pass


class BaseDictDescriber(AbstractDescriber):
    __slots__ = ("data", "current_listing")

    def __init__(self):
        self.data = {"version": 1, "groups": []}
        self.current_listing = None

    def _add_group(self, annotation: Optional[str] = None):
        listing = []
        self.data["groups"].append(
            {"annotation": annotation, "options": listing}
        )
        self.current_listing = listing

    def annotate(self, annotation: str):
        self._add_group(str(annotation))

    def add_option(self, key: Key, option: Option):
        if self.current_listing is None:
            self._add_group()
        assert self.current_listing is not None

        data: Dict[str, Any] = {
            "key": str(key),
        }
        if option.has_default():
            data["default"] = option.default

        validators = option.get_validators()
        if validators:
            data["validators"] = validators

        if option._has_flag(Flag.disabled):
            data["disabled"] = True
        if option._has_flag(Flag.ignored):
            data["ignored"] = True
        if option._has_flag(Flag.internal):
            data["internal"] = True
        if option._has_flag(Flag.experimental):
            data["experimental"] = True
        if option.description:
            data["description"] = option.description

        self.current_listing.append(data)


class DictDescriber(BaseDictDescriber):
    __slots__ = ()

    def finalize(self) -> str:
        import pprint

        return pprint.pformat(self.data)


class TomlDescriber(BaseDictDescriber):
    __slots__ = ()

    def finalize(self) -> str:
        import toml

        return toml.dumps(self.data)


class JsonDescriber(BaseDictDescriber):
    __slots__ = ()

    def finalize(self) -> str:
        import json

        return json.dumps(self.data)


class YamlDescriber(BaseDictDescriber):
    __slots__ = ()

    def finalize(self) -> str:
        import yaml

        return yaml.safe_dump(self.data)


class PythonDescriber(AbstractDescriber):
    __slots__ = ("output",)

    def __init__(self):
        self.output = StringIO()

    def finalize(self) -> str:
        return self.output.getvalue()

    def annotate(self, annotation: str):
        self.output.write(f"\ndeclaration.annotate({repr(annotation)})\n")

    def add_option(self, key: Key, option: Option):
        default = f", {repr(option.default)}" if option.has_default() else ""
        self.output.write(f"declaration.declare(key.{key}{default})")
        if option._has_flag(Flag.disabled):
            self.output.write(".disable()")
        if option._has_flag(Flag.ignored):
            self.output.write(".ignore()")
        if option._has_flag(Flag.internal):
            self.output.write(".internal()")
        if option._has_flag(Flag.experimental):
            self.output.write(".experimental()")
        if option.description:
            self.output.write(f".set_description({repr(option.description)})")

        validators = option.get_validators()
        if validators:
            self.output.write(f".set_validators({repr(validators)})")

        self.output.write("\n")
