pushd sample_data/scripts/
echo "Download eAIP locally"
./download_all.sh
popd

pushd src
echo "Generate JSON from eAIP"
python3 generate_json_from_eaip.py

echo "Generate KML from JSON"
python3 generate_kml_from_json.py
popd