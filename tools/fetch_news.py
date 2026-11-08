"""Fetch forestry headlines for every area and write news.json for the iPhone (web) version.

Runs daily on GitHub Actions (.github/workflows/news.yml) because Safari cannot read Google News
directly. Uses the same queries and forestry filter as the Android app's live news.

Usage: python3 fetch_news.py <places.json> <out news.json>
"""
import json, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

TERMS = '(forestry OR forest OR sawmill OR mill OR logging OR timber OR lumber OR "wood products")'
RES_TERMS = '(forestry OR forest OR logging OR timber OR mill OR mining OR mine OR minerals OR pipeline OR LNG OR "natural gas" OR hydro OR "Site C" OR wildfire OR "land use" OR stewardship OR "natural resource")'
FORESTRY_RE = re.compile(r"\b(forest\w*|sawmills?|mills?|logging|loggers?|logs|timber|lumber|wood|woodlots?|softwood|pulp|fibre|fiber|tenures?|harvest\w*|reforest\w*|silvicultur\w*|stumpage|old[- ]growth|cutblocks?|cutting permits?|planers?|pellets?|biomass|truck loggers?|COFI)\b", re.I)
RESOURCE_RE = re.compile(FORESTRY_RE.pattern.replace(')\\b', '|minings?|mines?|minerals?|pipelines?|LNG|gas|hydro|dams?|Site C|wildfires?|land[- ]use|stewardship|resources?|caribou|energy)\\b'), re.I)
UA = 'BC-Local-Leaders-news/1.0'

def rd_short(rd):
    s = re.sub(r'\s*\(Regional District\)$', '', rd or '')
    s = re.sub(r'^Regional District of\s+', '', s, flags=re.I)
    s = re.sub(r'\s+Regional District$', '', s, flags=re.I)
    return 'Capital Regional District' if s == 'Capital' else s

def queries(p):
    rd = rd_short(p.get('rd') or p['jurisdiction'])
    if p['type'] == 'muni':
        local, label = f'"{p["name"]}" ("B.C." OR BC OR "British Columbia")', p['name']
    else:
        m = re.search(r'\((.*)\)$', p['name'])
        locs = [x.strip() for x in re.split(r'\s*[/,]\s*|\s+and\s+', m.group(1))] if m else []
        locs = [x for x in locs if len(x) > 2][:4]
        local = '(' + ' OR '.join(f'"{x}"' for x in locs) + ')' if locs else f'"{rd}"'
        label = ', '.join(locs) if locs else rd
    names = [re.sub(r'\s*\(.*\)$', '', p['name']), rd] + label.split(', ')
    return rd, names, f'{local} {TERMS} when:120d', f'"{rd}" {TERMS} when:120d'

_cache = {}
def fetch(q):
    if q in _cache: return _cache[q]
    url = 'https://news.google.com/rss/search?q=' + urllib.parse.quote(q) + '&hl=en-CA&gl=CA&ceid=CA:en'
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=30) as r:
                root = ET.fromstring(r.read())
            break
        except Exception:
            time.sleep(10 * (attempt + 1))
    else:
        _cache[q] = None; return None
    items = []
    for it in root.iter('item'):
        src = it.find('source'); outlet = (src.text or '').strip() if src is not None else ''
        title = (it.findtext('title') or '').strip()
        if outlet and title.endswith(' - ' + outlet): title = title[:-(len(outlet) + 3)]
        try: t = int(parsedate_to_datetime(it.findtext('pubDate')).timestamp() * 1000)
        except Exception: t = 0
        link = (it.findtext('link') or '').strip()
        if title and link.startswith('https://'): items.append({'title': title, 'outlet': outlet, 'url': link, 't': t})
    time.sleep(1.2)  # be gentle with Google News
    _cache[q] = items
    return items

def relevant(items, names, scope, rx=None):
    rx = rx or FORESTRY_RE
    out = []
    for i in items or []:
        t = i['title']
        for n in names:
            if n: t = t.replace(n, ' ')
        if rx.search(t): out.append(dict(i, scope=scope))
    return out

def main():
    places = json.load(open(sys.argv[1]))['places']
    areas, failed = {}, 0
    for k, p in places.items():
        rd, names, ql, qr = queries(p)
        local = fetch(ql)
        if local is None: failed += 1
        items = relevant(local, names, 'local')
        if len(items) < 4:
            seen = {i['title'] for i in items}
            items += [i for i in relevant(fetch(qr), names, 'regional') if i['title'] not in seen]
        items.sort(key=lambda i: (0 if i['scope'] == 'local' else 1, -i['t']))
        areas[k] = {'rd': rd, 'items': items[:6]}
    # Partner First Nations (FN Partners): resource-wide news, past year, no regional fallback
    import os
    fn_path = os.path.join(os.path.dirname(sys.argv[1]), 'fn.json')
    if os.path.exists(fn_path):
        for k, n in json.load(open(fn_path))['nations'].items():
            short = re.sub(r'\s+(Indian Band|First Nation|Nation)$', '', n['name'])
            q = '(' + ' OR '.join(f'"{x}"' for x in n['newsNames']) + f') {RES_TERMS} when:365d'
            items = relevant(fetch(q), n['newsNames'] + [n['name'], short], 'local', RESOURCE_RE)
            items.sort(key=lambda i: -i['t'])
            areas[k] = {'rd': None, 'items': items[:6]}
    if failed > len(places) // 2:
        raise SystemExit(f'Google News failed for {failed} areas; keeping the previous news.json')
    json.dump({'updated': int(time.time() * 1000), 'areas': areas}, open(sys.argv[2], 'w'), separators=(',', ':'), ensure_ascii=False)
    print(f'news.json: {len(areas)} areas, {sum(len(a["items"]) for a in areas.values())} stories, {failed} failed lookups')

if __name__ == '__main__':
    main()
