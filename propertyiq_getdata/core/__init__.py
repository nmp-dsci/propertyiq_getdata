"""Reusable pipeline mechanics shared across sources.

These modules know nothing about any specific source — they handle data-dir
resolution, atomic CSV writes, and manifest generation. Source-specific logic
lives in :mod:`propertyiq_getdata.sources`.
"""
