# Copyright 2021 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""ProtoConverter.

This module provides a class to convert between different protos of
different types. All fields with the same name and type will be converted
automatically. Handler functions can be provided for custom conversions. Fields
can also be ignored.

  Typical usage example:

  converter = ProtoConverter(
        pb_class_from=proto1_pb2.Proto1,
        pb_class_to=proto2_pb2.Proto2,
        field_names_to_ignore=["field1", "field2"])
  proto2 = converter.convert(proto1)
"""

import functools
from typing import Any, Callable, List, Optional, Type

from google.protobuf import any_pb2
from google.protobuf import descriptor
from google.protobuf import symbol_database

# We would like to annotate FROM and TO as subclasses of message.Message but not
# message.Message itself. There currently exists no way to express such a thing,
# and using Message would lead to unwanted type errors, so Any is the best we
# can do.
FROM = Any
TO = Any


class ProtoConverter(object):
  """A converter to convert Protos in Python."""

  def __init__(self,
               pb_class_from: Type[FROM],
               pb_class_to: Type[TO],
               field_names_to_ignore: Optional[List[str]] = None):
    """Constructor for the ProtoConverter.

    Args:
      pb_class_from: the init method for the proto to convert from.
      pb_class_to: the init method for the proto to convert to.
      field_names_to_ignore: the fields from the source proto that will be
        ignored by the converter.

    Returns:
      ProtoConverter

    Raise:
      NotImplementedError: When creating the proto converter if there are
      fields not handled or ignored.

    """

    if field_names_to_ignore is None:
      field_names_to_ignore = []

    self._pb_class_from = pb_class_from
    self._pb_class_to = pb_class_to
    self._field_names_to_ignore = field_names_to_ignore
    self._function_convert_field_names = []  # type: List[str]
    self._convert_functions = []  # type: List[Callable]

    self._assert_all_fields_are_handled()

  def _assert_all_fields_are_handled(self):
    """Asserts all unhandled fields has been handled by user functions."""

    for entry in dir(self.__class__):
      function = getattr(self.__class__, entry)
      if not callable(function):
        continue

      if hasattr(function, "convert_field_names"):
        self._convert_functions.append(function)
        self._function_convert_field_names.extend(function.convert_field_names)

    src_proto_fields = self._pb_class_from.DESCRIPTOR.fields
    dest_proto_fields_by_name = self._pb_class_to.DESCRIPTOR.fields_by_name

    self._unconverted_fields = _get_unhandled_fields(
        src_proto_fields, dest_proto_fields_by_name,
        self._field_names_to_ignore)

    if self._pb_class_from.DESCRIPTOR.oneofs:
      _validate_oneof_field_multi_mapping(self._pb_class_from,
                                          self._pb_class_to,
                                          self._field_names_to_ignore)
    if self._pb_class_to.DESCRIPTOR.oneofs:
      _validate_oneof_field_multi_mapping(self._pb_class_to,
                                          self._pb_class_from,
                                          self._field_names_to_ignore)

    unconverted_fields = (
        set(self._unconverted_fields) - set(self._function_convert_field_names))

    if unconverted_fields:
      raise NotImplementedError(
          "Fields can't be automatically converted, must either be explicitly "
          "handled or explicitly ignored. Unhandled fields: {}.".format(
              unconverted_fields))

  def convert(self, src_proto: FROM) -> TO:
    """Converts the src_proto(pb_class_from) to the converter's pb_class_to."""

    src_type = src_proto.DESCRIPTOR.full_name
    expected_src_type = self._pb_class_from.DESCRIPTOR.full_name
    if src_type != expected_src_type:
      raise TypeError(
          f"Provided src_proto type [{src_type}] doesn't match the converter's "
          f"src_proto type [{expected_src_type}].")

    dest_proto = self._pb_class_to()

    self._auto_convert(src_proto, dest_proto)
    for user_func in self._convert_functions:
      user_func(self, src_proto, dest_proto)

    return dest_proto

  def _auto_convert(self, src_proto, dest_proto):
    """Auto-converts fields from src_proto to dest_proto."""

    for src_field_descriptor, src_field in src_proto.ListFields():
      if (src_field_descriptor.name in self._field_names_to_ignore or
          src_field_descriptor.name in self._unconverted_fields):
        continue

      dest_field_descriptor = dest_proto.DESCRIPTOR.fields_by_name[
          src_field_descriptor.name]
      dest_field = getattr(dest_proto, src_field_descriptor.name)

      # Map Case
      if _is_map_field(src_field_descriptor):
        src_map_value_field_descriptor = (
            src_field_descriptor.message_type.fields_by_name["value"])
        dest_map_value_field_descriptor = (
            dest_field_descriptor.message_type.fields_by_name["value"])
        # Map<key, Proto> -> Map<key, Any>
        if (_is_any_field(dest_map_value_field_descriptor) and
            not _is_any_field(src_map_value_field_descriptor)):
          for key, value in src_field.items():
            dest_field[key].Pack(value)

        # Map<key, Any> -> Map<key, Any> and Map<key, Proto> -> Map<key, Proto>
        else:
          dest_field.MergeFrom(src_field)

      # Array Case
      elif (src_field_descriptor.label ==
            descriptor.FieldDescriptor.LABEL_REPEATED):
        # Any[] -> Any[], MergeFrom doesn't work for Any[]
        # Any[] -> Proto[] shouldn't happen
        if _is_any_field(src_field_descriptor):
          factory = symbol_database.Default()
          for field in src_field:
            type_name = field.TypeName()
            proto_descriptor = factory.pool.FindMessageTypeByName(type_name)
            proto_class = factory.GetPrototype(proto_descriptor)
            proto_object = proto_class()
            field.Unpack(proto_object)
            dest_field.add().Pack(proto_object)
        #  Proto [] -> Any[]
        elif _is_any_field(dest_field_descriptor):
          for field in src_field:
            any_proto = any_pb2.Any()
            any_proto.Pack(field)
            dest_field.append(any_proto)
        else:
          dest_field.MergeFrom(src_field)

      # Proto Case
      elif src_field_descriptor.type == descriptor.FieldDescriptor.TYPE_MESSAGE:
        if _is_any_field(
            dest_field_descriptor) and not _is_any_field(src_field_descriptor):
          dest_field.Pack(src_field)
        else:
          dest_field.CopyFrom(src_field)

      # Other Case
      else:
        setattr(dest_proto, src_field_descriptor.name, src_field)


def _get_unhandled_fields(src_proto_fields, dest_proto_fields_by_name,
                          field_names_to_ignore):
  """Gets a list of unconverted fields from src to dest."""

  unhandled_field_names = []
  for field in src_proto_fields:
    if field.name in field_names_to_ignore:
      continue

    if not _is_src_field_auto_convertible(field, dest_proto_fields_by_name):
      unhandled_field_names.append(field.name)

  return unhandled_field_names


def _is_src_field_auto_convertible(src_field,
                                   dest_proto_fields_by_name) -> bool:
  """Checks if the src_field can be auto-converted.

  There must be a field in dest_proto with same name and type as the src_field
  to auto convert src_field.

  Args:
    src_field: the field to check if it's auto-convertible.
    dest_proto_fields_by_name: field name to field dict for dest_proto.

  Returns:
    bool: True if the src_field is auto-convertible.
  """

  if src_field.name not in dest_proto_fields_by_name:
    return False

  dest_field = dest_proto_fields_by_name[src_field.name]

  # Check field type and repeated label matching.
  if dest_field.label != src_field.label or src_field.type != dest_field.type:
    return False

  if _is_map_field(src_field):
    # Check that map field key and value are auto-convertible.
    src_fields_by_name = src_field.message_type.fields_by_name
    dest_fields_by_name = dest_field.message_type.fields_by_name
    if (not _is_src_field_auto_convertible(src_fields_by_name["key"],
                                           dest_fields_by_name) or
        not _is_src_field_auto_convertible(src_fields_by_name["value"],
                                           dest_fields_by_name)):
      return False
  elif src_field.type == descriptor.FieldDescriptor.TYPE_MESSAGE:
    # Any -> Any will always be valid
    if _is_any_field(src_field) and _is_any_field(dest_field):
      return True

    # Disable Any -> Proto convert since we can't check
    # whether it's convertible until runtime.
    if _is_any_field(src_field):
      return False

    # Proto -> Any will always be convertible as long as the field_name matches
    if _is_any_field(dest_field):
      return True

    if src_field.message_type != dest_field.message_type:
      return False

  return True


def _validate_oneof_field_multi_mapping(src_pb, dest_pb, ignored_fields):
  """Validates if the oneof field on src_pb maps to multiple fields.

  Args:
    src_pb: the proto to check oneof from.
    dest_pb: the proto to check oneof against.
    ignored_fields: fields that skip the check.
  Exception: Raises NotImplementedError if any oneof field in src_pb maps to
    multiple fields from dest_pb.
  """

  ignored_fields_set = set(ignored_fields)
  src_oneof_names_dict = src_pb.DESCRIPTOR.oneofs_by_name

  dest_oneof_dict = _get_fields_to_oneof_dict(dest_pb.DESCRIPTOR.oneofs_by_name)
  dest_field_names = set(dest_pb.DESCRIPTOR.fields_by_name.keys())

  for src_oneof_name, src_oneof_field in src_oneof_names_dict.items():
    mapped_field = set()
    for src_field in src_oneof_field.fields:
      src_field_name = src_field.name
      if src_field_name in ignored_fields_set:
        continue

      if src_field_name in dest_oneof_dict:
        mapped_field.add(dest_oneof_dict[src_field_name])
      elif src_field_name in dest_field_names:
        mapped_field.add(src_field_name)

    if len(mapped_field) > 1:
      raise NotImplementedError(
          "Oneof field {} in proto {} maps to more than one field, all fields in the "
          "oneof must be explicitly handled or ignored.".format(
              src_oneof_name, src_pb.DESCRIPTOR.name))


def _get_fields_to_oneof_dict(oneof_by_name):
  result_dict = {}
  for name, oneof_field in oneof_by_name.items():
    for field in oneof_field.fields:
      result_dict[field.name] = name

  return result_dict


def convert_field(field_names: Optional[List[str]] = None):
  """Decorator that converts proto fields.

  Args:
    field_names: list of field names from src proto this function handles.

  Returns:
    convert_field_decorator

  Typical usage example:

    @converter.convert_field(field_names=["hello"])
    def hello_convert_function(self, src_proto, dest_proto):
      ...
  """

  if field_names is None:
    field_names = []

  def convert_field_decorator(convert_method):
    convert_method.convert_field_names = field_names

    @functools.wraps(convert_method)
    def convert_field_wrapper(self, src_proto, dest_proto):
      convert_method(self, src_proto, dest_proto)

    return convert_field_wrapper

  return convert_field_decorator


def _is_any_field(field_descriptor) -> bool:
  return (field_descriptor.message_type ==
          any_pb2.DESCRIPTOR.message_types_by_name["Any"])


def _is_map_field(field_descriptor) -> bool:
  return (field_descriptor.label == descriptor.FieldDescriptor.LABEL_REPEATED
          and
          field_descriptor.type == descriptor.FieldDescriptor.TYPE_MESSAGE and
          field_descriptor.message_type.has_options and
          field_descriptor.message_type.GetOptions().map_entry)
