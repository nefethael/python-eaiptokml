# How to generate France border

Download IGN Admin Express [SHP file](https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS/ADMIN-EXPRESS_3-2__SHP_LAMB93_FXX_2025-02-17/ADMIN-EXPRESS_3-2__SHP_LAMB93_FXX_2025-02-17.7z).

Install [mapshaper](https://github.com/mbloch/mapshaper)

Reduce map with command: 

```
mapshaper -i REGION.shp snap -proj wgs84 -simplify 0.05% weighted keep-shapes -dissolve2 -filter-islands min-vertices 3000000 -o format=geojson precision=0.00001 metropole-version-simplifiee.geojson
```

# How to generate territorial water limits

Download SHOM [SHP files](https://services.data.shom.fr/INSPIRE/telechargement/prepackageGroup/ESPACES_MARITIMES_PACK_DL/prepackage/ESPACES_MARITIMES/file/ESPACES_MARITIMES.7z)

Reduce maps with commands:

```
# exclusive economic zone
mapshaper -i ./3_zone_economique_exclusive/SHAPE/EspMar_FR_ZEE_WGS84.shp snap -proj wgs84 -clip bbox="-14,38,11,52" -dissolve2 -simplify 4% weighted keep-shapes -o format=geojson precision=0.00001 -o EspMar_FR_ZEE_WGS84.json

# territorial sea
mapshaper -i ./1_mer_territoriale/SHAPE/EspMar_FR_MT_WGS84.shp snap -proj wgs84 -clip bbox="-14,38,11,52" -filter-islands min-vertices 2000 -dissolve2 -simplify 1% weighted keep-shapes -o format=geojson precision=0.00001 -o EspMar_FR_MT_WGS84.json
```