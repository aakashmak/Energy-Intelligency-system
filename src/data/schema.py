"""
Supabase schema — table definitions and region seed data.
The SQL in schema.sql must be run once in the Supabase SQL Editor.
"""

REGION_META = [
    ("Permian",     "TX,NM",    "shale",        31.9,  -102.3),
    ("Bakken",      "ND,MT",    "shale",        47.8,  -103.4),
    ("Eagle Ford",  "TX",       "shale",        28.4,   -98.1),
    ("Appalachia",  "WV,PA,OH", "shale",        39.5,   -80.2),
    ("Gulf Coast",  "LA,TX",    "conventional", 28.0,   -90.5),
]
