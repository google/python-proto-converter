
# Python Proto Converter
The Python Proto Converter converts between protos in Python. Proto conversion is often needed when converting between Database Access Object (DAO) and API proto.

### Install
pip install python-proto-converter

### Run the example
1. Build the proto (assuming in exmaple/ directory)
   protoc -I=. --python_out=. ./example_proto.proto

2. execute
   python3 ./converter_example.py

### Features

*   A base class that auto-converts fields with the same name and type.
*   Custom convert functions can be implemented to handle fields conversion.
*   Fields can be disabled during auto-converting.
*   Unhandled fields assertion during class instantiation.

### Example

#### Basic usage

Let's start with a simple example, suppose you want to convert from one similar
proto to another. For this example, these are the MatchaMilkTea to
GreenTeaMilkTea protos.

```proto
message MatchaMilkTea {
  string name = 1;
  float price = 2;
  string seller = 3;
}
```

```proto
message GreenTeaMilkTea {
  string name = 1;
  int64 price = 2;
  string seller = 3;
}
```

The `name` and `seller` fields can be auto-converted, since the type and the
field name are identical. However, we probably don't want to copy the name of
MatchaMilkTea to GreenTeaMilkTea. To disable auto-convert on the `name` field,
we mark it ignored and provide our custom function for the `name` field.

The `price` field has different types (float vs int64), therefore it can't be
auto-converted. Leaving it unhandled will trigger an exception when creating the
proto converter. Similar to the `name` field, we can create a custom method to
convert the `price` field.

```python
from google3.alkali.contrib.certified.python.proto import converter

...

class MatchaToGreenTeaConverter(converter.ProtoConverter):
  def __init__(self):
    super(MatchaToGreenTeaConverter, self).__init__(
        pb_class_from=matcha_milk_tea_pb2.MatchaMilkTea,
        pb_class_to=green_tea_milk_tea_pb2.GreenTeaMilkTea,
        field_names_to_ignore=["name"])

  @converter.convert_field(field_names=["price"])
  def price_convert_function(self, src_proto, dest_proto):
    dest_proto.price = int(src_proto.price)

  @converter.convert_field(field_names=["name"])
  def name_convert_function(self, src_proto, dest_proto):
    dest_proto.name = "GreenTeaMilkTea"
```

Or you can combine them in the same method since these fields are simple:

```python
@converter.convert_field(field_names=["price", "name"])
def price_name_convert_function(self, src_proto, dest_proto):
  dest_proto.price = int(src_proto.price)
  dest_proto.name = "GreenTeaMilkTea"
```

Now you can create the converter in code and use it:

```python
...
matcha_to_green_tea_converter = MatchaToGreenTeaConverter()
green_tea_milk_tea_proto = matcha_to_green_tea_converter.convert(matcha_milk_tea_proto)
...
```

#### Nested protos

Let's make this example a bit more complicated by adding some fields.

```proto
enum Flavor {
  GREEN_TEA = 0;
  MATCHA = 1;
  BERRY = 2;
  SPICY = 3;
}

message MilkTea {
  string name = 1;
  float price = 2;
  Flavor flavor = 3;
}
```

```proto
message MatchaMilkTea {
  MilkTea milk_tea = 1;
  int64 sugar = 2;
  repeated string shops = 3;
  string matcha_provider = 4;
  map<string, int64> ingredients = 5;
  map<string, string> ingredients_calorie_map = 6;
  repeated string cup_sizes = 7;
}
```

```proto
message GreenTeaMilkTea {
  MilkTea milk_tea = 1;
  float sugar = 2;
  repeated string shops = 3;
  string green_tea_provider = 4;
  map<string, int64> ingredients = 5;
  map<string, int32> ingredients_calorie_map = 6;
  repeated int64 cup_sizes = 7;
}
```

Most of the fields are identical and can be auto-converted, except:

*   float sugar and int64 sugar;
*   string green_tea_provider;
*   string matcha_provider;
*   ingredients_calorie_map;
*   cup_sizes;

You can create a new MatchaToGreenTeaConverter class that inherits ProtoConverter
to convert from MatchaMilkTea to GreenTeaMilkTea:

```python
from google3.alkali.contrib.certified.python.proto import converter

...

class MatchaToGreenTeaConverter(converter.ProtoConverter):
  def __init__(self):
    super(MatchaToGreenTeaConverter, self).__init__(
        pb_class_from=matcha_milk_tea_pb2.MatchaMilkTea,
        pb_class_to=green_tea_milk_tea_pb2.GreenTeaMilkTea,
        field_names_to_ignore=["ingredients_calorie_map", "cup_sizes"])

  @converter.convert_field(field_names=["sugar"])
  def sugar_convert_function(self, src_proto, dest_proto):
    dest_proto.sugar = int(src_proto.sugar)

  @converter.convert_field(field_names=["matcha_provider"])
  def provider_convert_function(self, src_proto, dest_proto):
    dest_proto.green_tea_provider = src_proto.matcha_provider
```

*   `pb_class_from` and `pb_class_to` are the constructors of the protos.
*   pb_class_from.Fields in `field_names_to_ignore` will be ignored during
    auto-conversion and when validating that all fields have been handled. In
    the example, `ingredients_calorie_map` and `cup_sizes` are ignored during
    conversion.
*   `@converter.convert_field` decorates a custom conversion function. In this
    example, we have two functions to convert the `sugar` field and the
    `matcha_provider` field.
*   All fields that can't be auto-converted from the source proto must either be
    handled by custom conversion functions or listed in `field_names_to_ignore`.

#### Oneof fields

Oneof fields can be tricky and error-prone, therefore it is required to
explicitly handle or ignore all the fields in oneofs.

```proto
message MochiFlavor {
  string flavor = 1;
}

message Mochi {
  oneof price {
    string price_str = 1;
    float price_float = 2;
  }
  oneof flavor {
    Flavor flavor_enum = 3;
    MochiFlavor flavor_proto = 4;
  }
  int64 calorie = 5;
}
```

```proto
message TaroMochi {
  float price_float = 1;
  MochiFlavor flavor_proto = 2;
  int64 calorie = 3;
}
```

```python
proto_converter = converter.ProtoConverter(
        pb_class_from=mochi_pb2.Mochi,
        pb_class_to=mochi_pb2.Taromochi,
        field_names_to_ignore=["flavor_enum", "price_str"])
src_proto = mochi_pb2.Mochi(
        price_float=3.14,
        flavor_proto=mochi_pb2.MochiFlavor(flavor="taro"),
        calorie=100)

dest_proto = proto_converter.convert(src_proto=src_proto)
```

In the above example, even though `flavor_enum` and `price_str` fields are not
used, ProtoConverter will still raise an exception if these fields are not
ignored.

#### Any fields

`Proto` to `Any` and `Any` to `Any` are converted automatically as long as the
field name matches.

```proto
message AnyMochiBox {
  string name = 1;
  google.protobuf.Any mochi = 2;
}

message TaroMochiBox {
  string name = 1;
  TaroMochi mochi = 2;
}
```

In the example below, ProtoConverter auto-converts a TaroMochi field to a Any
field.

```python
taro_mochi = mochi_pb2.TaroMochi(price_float=3.14,
flavor_proto=mochi_pb2.MochiFlavor(flavor="taro"), calorie=100)
proto_converter = converter.ProtoConverter(
pb_class_from=mochi_pb2.TaroMochiBox, pb_class_to=mochi_pb2.AnyMochiBox)

src_proto = mochi_pb2.TaroMochiBox(name="TaroMochiBox", mochi=taro_mochi)

dest_proto = proto_converter.convert(src_proto=src_proto)
```

Similarily, ProtoConverter auto-converts Proto Any field to Any field.

```python
taro_mochi = mochi_pb2.TaroMochi(
        price_float=3.14,
        flavor_proto=mochi_pb2.MochiFlavor(flavor="taro"),
        calorie=100)
taromochi_any_proto = any_pb2.Any()
taromochi_any_proto.Pack(taro_mochi)
proto_converter = converter.ProtoConverter(
    pb_class_from=mochi_pb2.AnyMochiBox, pb_class_to=mochi_pb2.AnyMochiBox)
src_proto = mochi_pb2.AnyMochiBox(
    name="TaroMochiBox", mochi=taromochi_any_proto)

dest_proto = proto_converter.convert(src_proto=src_proto)
```

Repeated `Any` field and Map `Any` field are also supported.

```proto
message AnyMochiBoxes {
  string name = 1;
  repeated google.protobuf.Any mochi = 2;
}

message TaroMochiBoxes {
  string name = 1;
  repeated TaroMochi mochi = 2;
}

message MochiGiftPackage {
  string name = 1;
  map<string, google.protobuf.Any> mochi = 2;
}

message TaroMochiGiftPackage {
  string name = 1;
  map<string, google.protobuf.Any> mochi = 2;
}
```

The examples below demonstrate the auto-conversion for repeated fields and Map
fields with Any proto.

```python
proto_converter = converter.ProtoConverter(
        pb_class_from=mochi_pb2.TaroMochiBoxes,
        pb_class_to=mochi_pb2.AnyMochiBoxes)
src_proto = mochi_pb2.TaroMochiBoxes(name="TaroMochiBoxes",
                                     mochi=[taro_mochi, taro_mochi])
dest_proto = proto_converter.convert(src_proto=src_proto)
```

```python
proto_converter = converter.ProtoConverter(
        pb_class_from=mochi_pb2.TaroMochiGiftPackage,
        pb_class_to=mochi_pb2.AnyMochiGiftPackage)
src_proto = mochi_pb2.TaroMochiGiftPackage(
    name="TaroMochiBoxes",
    mochi={"taro_mochi": taro_mochi})
dest_proto = proto_converter.convert(src_proto=src_proto)
```

We decided not to support `Any` field to `Proto` field auto conversion to make
it less error-pone, since the `Any` field can contain any type and cause runtime
failures. However, it is very easy to add a custom method to handle `Any` field.

```python
class MochiConverter(converter.ProtoConverter):

  @converter.convert_field(field_names=["mochi"])
  def mochi_field_convert_function(self, src_proto, dest_proto):
    src_proto.mochi.Unpack(dest_proto.mochi)

...

taro_mochi = mochi_pb2.TaroMochi(
        price_float=3.14,
        flavor_proto=mochi_pb2.MochiFlavor(flavor="taro"),
        calorie=100)
taromochi_any_proto = any_pb2.Any()
taromochi_any_proto.Pack(taro_mochi)
proto_converter = MochiConverter(pb_class_from=mochi_pb2.AnyMochiBox,
                                 pb_class_to=mochi_pb2.TaroMochiBox)
src_proto = mochi_pb2.AnyMochiBox(
        name="TaroMochiBox", mochi=_pack_to_any_proto(taro_mochi))

dest_proto = proto_converter.convert(src_proto=src_proto)
```

Repeated `Any` field to repeated `Proto` field

```python
class RepeatedMochiConverter(converter.ProtoConverter):

  @converter.convert_field(field_names=["mochi"])
  def mochi_field_convert_function(self, src_proto, dest_proto):
    for field in src_proto.mochi:
      proto_object = mochi_pb2.TaroMochi()
      field.Unpack(proto_object)
      dest_proto.mochi.append(proto_object)
```

Map `Any` field to Map `Proto` field

```python
class MapMochiConverter(converter.ProtoConverter):

  @converter.convert_field(field_names=["mochi"])
  def mochi_field_convert_function(self, src_proto, dest_proto):
    for key, field in src_proto.mochi.items():
      proto_object = mochi_pb2.TaroMochi()
      field.Unpack(proto_object)
      dest_proto.mochi[key].CopyFrom(proto_object)
```

#### Nested conversion

Nested conversion is supported if the source proto and destination proto
contains the same proto type (like the above example),
while auto-conversion won't work if the nested protos are of different type.

However, it's very easy to support this case with a custom method. We think it's
cleaner to create separate converters as you will see in the below example.

```proto
message TaroMochi {
  float price_float = 1;
  MochiFlavor flavor_proto = 2;
  int64 calorie = 3;
}

message CocoMochi {
  float price_float = 1;
  MochiFlavor flavor_proto = 2;
  int64 calorie = 3;
}

message TaroMochiBox {
  string name = 1;
  TaroMochi mochi = 2;
}

message CocoMochiBox {
  string name = 1;
  CocoMochi mochi = 2;
}
```

```python
class NestedMochiBoxConverter(converter.ProtoConverter):
  taro_to_coco_converter: converter.ProtoConverter = None

  def __init__(self):
    super(RecursiveMochiBoxConverter, self).__init__(
        pb_class_from=mochi_pb2.TaroMochiBox,
        pb_class_to=mochi_pb2.CocoMochiBox
    )
    self.taro_to_coco_converter = converter.ProtoConverter(
        pb_class_from=mochi_pb2.TaroMochi, pb_class_to=mochi_pb2.CocoMochi)

  @converter.convert_field(field_names=["mochi"])
  def mochi_field_convert_function(self, src_proto, dest_proto):
    dest_proto.mochi.CopyFrom(
      self.taro_to_coco_converter.convert(src_proto.mochi))

...

proto_converter = NestedMochiBoxConverter()
dest_proto = proto_converter.convert(src_proto)
```

With the additional ProtoConverter between TaroMochi and CocoMochi, it's very
easy to update the conversion once the TaroMochi or CocoMochi proto changes.

For nested array protos, we need to iterate through each element and append the
conversion result to the destination proto:

```proto
message CocoMochiBoxes {
  string name = 1;
  repeated CocoMochi mochi = 2;
}

message TaroMochiBoxes {
  string name = 1;
  repeated TaroMochi mochi = 2;
}
```

```python
@converter.convert_field(field_names=["mochi"])
def mochi_field_convert_function(self, src_proto, dest_proto):
  for mochi in src_proto.mochi:
    dest_proto.mochi.append(self.taro_to_coco_converter.convert(mochi))
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for details.

## License

Apache 2.0; see [`LICENSE`](LICENSE) for details.

## Disclaimer

This project is not an official Google project. It is not supported by
Google and Google specifically disclaims all warranties as to its quality,
merchantability, or fitness for a particular purpose.
