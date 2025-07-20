VERSION="eAIP_07_AUG_2025/FRANCE/AIRAC-2025-08-07"


############################################################################
URL="https://www.sia.aviation-civile.gouv.fr/media/dvd/${VERSION}/html/eAIP"


############################################################################
echo "Refreshing airports/heliports:" 

curl -s "${URL}/FR-menu-fr-FR.html"  -o FR-menu-fr-FR.html

cat FR-menu-fr-FR.html | sed 's/^.*a href="\(FR-AD[^"]*"\) .*$/\1/g'  | sort -u | sed 's/#.*$//g' | egrep '^FR-AD-2.LF|^FR-AD-3.LF' | sort -u > airport_list.txt

cat airport_list.txt | while read f;
do 
  echo " - $f" 
  curl -s "${URL}/$f"  -o "../AD-2-AERODROMES/$f"
done

echo ""

############################################################################
echo "Refreshing ENRs:" 
echo " - FR-ENR-2.1-fr-FR.html"
curl -s "${URL}/FR-ENR-2.1-fr-FR.html"  -o "../ENR-2.1-FIR_UIR_TMA_CTA/FR-ENR-2.1-fr-FR.html"

echo " - FR-ENR-2.2-fr-FR.html"
curl -s "${URL}/FR-ENR-2.2-fr-FR.html"  -o "../ENR-2.2-TMZ_ACC_UAC_APP_FRA_DLG_SIV/FR-ENR-2.2-fr-FR.html"

echo " - FR-ENR-5.1-fr-FR.html"
curl -s "${URL}/FR-ENR-5.1-fr-FR.html"  -o "../ENR-5.1-ZI_ZR_ZD/FR-ENR-5.1-fr-FR.html"

echo "" 

#############################################################################
echo "Remove unwanted strings"
find ../ -name '*.html' | while read f; do sed -e 's/<del class.*<\/del>//g' -i $f; done