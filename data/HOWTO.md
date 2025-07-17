# How to generate France border

Download IGN Admin Express [SHP file](https://data.geopf.fr/telechargement/download/ADMIN-EXPRESS/ADMIN-EXPRESS_3-2__SHP_LAMB93_FXX_2025-02-17/ADMIN-EXPRESS_3-2__SHP_LAMB93_FXX_2025-02-17.7z).

Install [mapshaper](https://github.com/mbloch/mapshaper)

Reduce map with command: 

```
mapshaper -i REGION.shp snap -proj wgs84 -simplify 0.05% weighted keep-shapes -dissolve2 -filter-islands min-vertices 3000000 -o format=geojson precision=0.00001 metropole-version-simplifiee.geojson
```
