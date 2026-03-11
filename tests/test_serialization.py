import json

from deepdiff import DeepHash

from cozystudio_addon.core.bpy_git import (
    default_json_decoder,
    normalize_json_data,
    serialize_json_data,
)


def test_serialization_round_trip():
    data = {
        "name": "Sample",
        "values": [1.0, 2.5, 3.1415926],
        "nested": {"b": 2, "a": 1},
        "blob": b"\x00\x01\x02",
    }

    serialized = serialize_json_data(data)
    decoded = default_json_decoder(json.loads(serialized))
    expected = default_json_decoder(normalize_json_data(data))

    assert decoded == expected


def test_hash_stability_with_order_and_float_precision():
    data1 = {"b": 2, "a": 1, "float": 1.23456789}
    data2 = {"a": 1, "float": 1.23456781, "b": 2}

    serialized1 = serialize_json_data(data1)
    serialized2 = serialize_json_data(data2)

    assert serialized1 == serialized2
    assert DeepHash(serialized1)[serialized1] == DeepHash(serialized2)[serialized2]
