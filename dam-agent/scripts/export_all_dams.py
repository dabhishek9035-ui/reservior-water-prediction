import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.getcwd())
from backend.models import DAM_METADATA

raw_places = {
  'almatti': (['Almatti', 'Muddebihal', 'Bagalkote'], ['Bagalkote', 'Vijayapura', 'Raichur', 'Yadgir'], 1708.0, 1570.0, 123.08, 123.08, 2.2, 36000, 1964, ['lal bahadur shastri sagar', 'almatti']),
  'bhadra': (['Lakkavalli', 'Bhadravathi', 'Tarikere'], ['Shivamogga', 'Chikkamagaluru', 'Davanagere'], 2158.0, 2070.0, 71.50, 71.50, 3.8, 19680, 1965, ['lakkavalli', 'bhadra']),
  'hemavathy': (['Gorur', 'Hassan', 'Holenarasipura'], ['Hassan', 'Mandya', 'Tumakuru'], 2922.0, 2780.0, 37.10, 37.10, 1.6, 28000, 1979, ['gorur', 'hemavathi']),
  'kabini': (['H D Kote', 'Nanjangud', 'Saragur'], ['Mysuru', 'Chamarajanagar'], 2284.0, 2180.0, 19.50, 19.50, 1.1, 21400, 1974, ['beechanahalli', 'kabini']),
  'krsagara': (['Srirangapatna', 'Mysuru', 'Mandya'], ['Mandya', 'Mysuru', 'Bengaluru South'], 124.8, 102.0, 105.79, 105.79, 8.4, 10700, 1932, ['krs', 'krishna raja sagara', 'kannambadi']),
  'linganamakki': (['Jog Falls', 'Sagara', 'Kargal'], ['Shivamogga', 'Uttara Kannada', 'Honnavar'], 1819.0, 1680.0, 156.61, 156.61, 5.8, 19900, 1964, ['sharavathi', 'linganamakki']),
  'malaprabha': (['Saundatti', 'Naviluteertha', 'Ramdurg'], ['Belagavi', 'Bagalkote', 'Dharwad'], 2079.5, 1960.0, 37.73, 37.73, 2.7, 11330, 1972, ['renuka sagar', 'naviluteertha', 'malaprabha']),
  'supa': (['Joida', 'Dandeli', 'Ganeshgudi'], ['Uttara Kannada', 'Karwar'], 1850.0, 1710.0, 147.53, 147.53, 6.7, 10500, 1980, ['kali', 'kalinadi', 'supa']),
  'tungabhadra': (['Hosapete', 'Hampi', 'Kamalapuram'], ['Vijayanagara', 'Koppal', 'Raichur', 'Ballari'], 1633.0, 1510.0, 100.80, 100.80, 5.2, 28000, 1953, ['pampa sagar', 'tb dam', 'tungabhadra']),
  'vanivilasa_sagar': (['Hiriyur', 'Challakere', 'Hosadurga'], ['Chitradurga', 'Tumakuru'], 130.0, 102.0, 30.40, 30.40, 2.1, 4890, 1907, ['mari kanive', 'vani vilasa sagar', 'hiriyur'])
}

latest_readings = {
  'almatti': {'date': '2026-09-27', 'level': 1698.4},
  'bhadra': {'date': '2026-09-27', 'level': 2147.7},
  'hemavathy': {'date': '2026-09-27', 'level': 2914.2},
  'kabini': {'date': '2026-09-27', 'level': 2278.6},
  'krsagara': {'date': '2026-09-27', 'level': 121.5},
  'linganamakki': {'date': '2026-09-27', 'level': 1807.3},
  'malaprabha': {'date': '2026-09-27', 'level': 2071.8},
  'supa': {'date': '2026-09-27', 'level': 1836.9},
  'tungabhadra': {'date': '2026-09-27', 'level': 1625.1},
  'vanivilasa_sagar': {'date': '2026-09-27', 'level': 124.6}
}

dams = []
for dam_id, meta in DAM_METADATA.items():
    places, regions, max_l, min_l, gross, live, dead, catchment, built, aliases = raw_places[dam_id]
    lr = latest_readings[dam_id]
    coords = meta.get('coordinates', {})
    dams.append({
        'id': dam_id,
        'name': meta.get('short_name', meta['name']),
        'reservoir': meta['name'],
        'river': meta['river'],
        'location': f"{meta['district']}, Karnataka",
        'district': meta['district'],
        'state': 'Karnataka',
        'lat': coords.get('lat'),
        'lng': coords.get('lon'),
        'yearBuilt': built,
        'purpose': meta['purpose'],
        'maxLevel': max_l,
        'minLevel': min_l,
        'unit': 'ft',
        'grossStorage': gross,
        'liveStorage': live,
        'deadStorage': dead,
        'catchmentArea': catchment,
        'nearbyPlaces': places,
        'affectedRegions': regions,
        'lastRecorded': lr,
        'aliases': aliases
    })

out_path = os.path.join(os.getcwd(), 'dam-agent', 'data', 'dams.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(dams, f, indent=2)
print(f"Successfully wrote {len(dams)} dams to {out_path}")
