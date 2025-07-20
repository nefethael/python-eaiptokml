cat airport_list.txt | while read f; do curl https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_10_JUL_2025/FRANCE/AIRAC-2025-07-10/html/eAIP/$f  -o $f ; done


