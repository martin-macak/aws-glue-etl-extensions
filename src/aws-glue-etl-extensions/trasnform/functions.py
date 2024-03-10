from typing import Optional, Callable

import awsglue.dynamicframe
import boto3
from boto3.dynamodb.types import TypeDeserializer

boto3.resource("dynamodb")
ddb_deserializer = boto3.dynamodb.types.TypeDeserializer()


def deserialize_ddb_item(rec):
    """
    Deserializes a DynamoDB record into a dictionary.
    Numbers are converted so Decimal is not used.

    :param rec: original DDB item
    :return: transformed item
    """

    item = rec["Item"]
    result = {k: ddb_deserializer.deserialize(v) for k, v in item.items()}
    return result


def pivot_map_to_list(
        obj: dict,
        path: list[str],
        to: Optional[list[str]] = None,
        lst_filter: Optional[Callable] = None,
):
    """
    Pivots a map of key/values into an array of items with keys and values.
    Keys are identified as "item_key" and values as "item_value".

    This transformation can also move the transformed field to new path.
    List members can be also filtered out by the lst_filter function.

    The transformation is performed in place so the original object is altered.

    :param obj: transformed object
    :param path: path to the map field
    :param to: new path for the transformed field. If None, the original path is used.
    :param lst_filter: filter function for list members
    :return: transformed object
    """

    if lst_filter is None:
        lst_filter = _truthy

    orig = obj
    src = orig
    for i, p in enumerate(path):
        nxt = src.get(p)
        if nxt is None:
            break
        if i == len(path) - 1:
            del src[p]
        src = nxt

    if src is None:
        return orig

    if not isinstance(src, dict):
        return orig

    lst = []
    for k, v in src.items():
        if not lst_filter(v):
            continue
        lst.append({"item_key": k, "item_value": v})

    if to is None:
        to = path

    dst = orig
    for i, p in enumerate(to):
        if i == len(to) - 1:
            dst[p] = lst
            break
        else:
            dst = dst.get(p)

    return orig


def spread_partition_keys(
        obj: dict,
        partition_keys: list[str],
) -> dict:
    """
    Spreads partition keys into the object collections.

    This transformation is useful when you want to relationalize the original dataframe
    and also want to keep the partition keys in the new objects.

    This transformation is performed in place so the original object is altered.

    :param obj: transformed object
    :param partition_keys: list of partition keys
    :return: transformed object
    """

    if not isinstance(obj, dict):
        return obj

    p_items = [
        (k, obj.get(k))
        for k in partition_keys
    ]

    def inject_keys(node):
        for k, v in p_items:
            node[k] = v
        return node

    def walk(node):
        if isinstance(node, list):
            for i, item in enumerate(node):
                if isinstance(item, dict):
                    inject_keys(item)
                walk(item)
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v)

        return node

    return walk(obj)


def root_partition_keys_on_rel(
        rel: awsglue.dynamicframe.DynamicFrameCollection,
        partition_keys: list[str],
) -> awsglue.dynamicframe.DynamicFrameCollection:
    """
    Roots partition keys on the relationalized collection of DataFrames.

    Use this function if you used `spread_partition_keys` to spread partition keys
    and then relationalized the original DataFrame.

    :param rel: list of relationalized data frames
    :param partition_keys: list of partition keys
    :return: altered relationalized data frames
    """

    if len(rel) == 0:
        return rel

    df_names = list(rel.keys())
    root_df_name = df_names[0]

    transformed_gdf_map = {}
    for df_name in df_names[1:]:
        df = rel[df_name]
        rel_df_name = df_name.lstrip(root_df_name).lstrip("_")
        for partition_key in partition_keys:
            field_name = _sanitize_name(f"{rel_df_name}.val.{partition_key}")
            transformed_df = df.rename_field(
                field_name,
                partition_key,
            )
            transformed_gdf_map[df_name] = transformed_df

    return awsglue.dynamicframe.DynamicFrameCollection(transformed_gdf_map)


# noinspection PyUnusedLocal
def _truthy(*args, **kwargs) -> bool:  # noqa
    return True


def _ddb_serde_number(number: str):
    if '.' in number:
        return float(number)
    return int(number)


def _sanitize_name(name: str):
    if "." in name:
        return f"`{name}`"
    else:
        return name


setattr(ddb_deserializer, '_deserialize_n', lambda number: _ddb_serde_number(number))
