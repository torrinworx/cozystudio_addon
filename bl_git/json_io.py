import base64
import json
import math

from .constants import FLOAT_PRECISION


def default_json_encoder(obj):
    if isinstance(obj, (bytes, bytearray)):
        return {"__bytes__": True, "data": base64.b64encode(obj).decode("ascii")}
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def default_json_decoder(obj):
    if isinstance(obj, dict):
        if obj.get("__bytes__") is True and "data" in obj:
            return base64.b64decode(obj["data"])
        return {k: default_json_decoder(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [default_json_decoder(x) for x in obj]
    return obj


def normalize_json_data(value):
    if isinstance(value, dict):
        normalized = {}
        for key in sorted(value.keys(), key=lambda k: str(k)):
            normalized[str(key)] = normalize_json_data(value[key])
        return normalized
    if isinstance(value, (list, tuple)):
        return [normalize_json_data(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return round(value, FLOAT_PRECISION)
    if isinstance(value, (bytes, bytearray)):
        return default_json_encoder(value)
    return value


def serialize_json_data(data) -> str:
    normalized = normalize_json_data(data)
    return json.dumps(
        normalized,
        indent=2,
        sort_keys=True,
        ensure_ascii=True,
        default=default_json_encoder,
    )
