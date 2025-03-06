"""Define common variable names in L2 granules required for gridded raster processing."""

L2_SCHEMAS: list[dict[str, str]] = [
    {
        "regex": r"OCO[23]_L2_Lite_SIF.*r",
        "file_regex": r"oco[23]_LtSIF",
        "lat": "Latitude",
        "lon": "Longitude",
        "vertex_lat": "Geolocation/footprint_latitude_vertices",
        "vertex_lon": "Geolocation/footprint_longitude_vertices"
    },
    {
        "regex": r"OCO[23]_L2_Lite_FP.*r",
        "file_regex": r"oco[23]_LtCO2",
        "lat": "latitude",
        "lon": "longitude",
        "vertex_lat": "vertex_latitude",
        "vertex_lon": "vertex_longitude"
    }
]