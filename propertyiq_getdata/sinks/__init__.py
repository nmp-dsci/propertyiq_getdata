"""Publish targets — the counterpart of :mod:`propertyiq_getdata.sources`.

Sources pull data in and write canonical CSV partitions; sinks take those
partitions and publish them somewhere else. The first sink is Databricks: it
converts new or changed partitions to Parquet and uploads them to a Unity
Catalog volume for an Auto Loader pipeline to ingest.
"""

from .databricks import publish_databricks

__all__ = ["publish_databricks"]
