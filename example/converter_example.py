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

import example_proto_pb2

from pyproto import converter
from google.protobuf import any_pb2


class MatchaToGreenTeaConverter(converter.ProtoConverter):
  def __init__(self):
    super(MatchaToGreenTeaConverter, self).__init__(
        pb_class_from=example_proto_pb2.MatchaMilkTea,
        pb_class_to=example_proto_pb2.GreenTeaMilkTea)

  @converter.convert_field(field_names=["name", "price"])
  def price_name_convert_function(self, src_proto, dest_proto):
    dest_proto.price = int(src_proto.price)
  
  @converter.convert_field(field_names=["topping1"])
  def topping_convert_function(self, src_proto, dest_proto):
    src_proto.topping1.Unpack(dest_proto.topping1)

def _pack_to_any_proto(proto):
  any_proto = any_pb2.Any()
  any_proto.Pack(proto)
  return any_proto

def example():
    src_milk_tea = example_proto_pb2.MatchaMilkTea(
      name="matcha_milk_tea", price=10, seller="sellerA", 
      topping1=_pack_to_any_proto(example_proto_pb2.Topping(name="jelly")),
      topping2=_pack_to_any_proto(example_proto_pb2.Topping(name="taro")), 
      topping3=example_proto_pb2.Topping(name="chips"))

    proto_converter = MatchaToGreenTeaConverter()

    result_proto = proto_converter.convert(src_milk_tea)

    print(result_proto)


if __name__ == '__main__':
    example()