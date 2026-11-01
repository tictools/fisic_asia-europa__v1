#!/usr/bin/env python3
"""
Generates the blank map data (data/europa.js and data/asia.js) from Natural Earth.

Usage:
    NE_DIR=/path/to/natural-earth-vector/geojson python3 tools/generate_maps.py

Only needs re-running to change features, base colours or the map framing.
The site doesn't need this script to work (the data files are already generated).
Requirements: Python 3 + numpy.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'data')
NE = os.environ.get('NE_DIR', os.path.join(HERE, 'natural-earth-vector', 'geojson'))


def load(n):
    with open(os.path.join(NE, n + '.geojson'), encoding='utf-8') as fh:
        return json.load(fh)['features']


LAND = load('ne_50m_land')
LAKES = load('ne_50m_lakes')
RIVERS = load('ne_10m_rivers_lake_centerlines')
REG = load('ne_10m_geography_regions_polys')
MAR = load('ne_50m_geography_marine_polys')
CTRY = load('ne_50m_admin_0_countries')

W = 1600  # viewBox width


# ---------------------------------------------------------------- projection
class LAEA:
    """Lambert azimuthal equal-area projection (km)."""

    def __init__(self, lon0, lat0):
        self.l0, self.p0 = np.radians(lon0), np.radians(lat0)

    def __call__(self, lon, lat):
        lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
        dl = lon - self.l0
        k = np.sqrt(2 / (1 + np.sin(self.p0) * np.sin(lat) + np.cos(self.p0) * np.cos(lat) * np.cos(dl)))
        return (k * np.cos(lat) * np.sin(dl) * 6371,
                k * (np.cos(self.p0) * np.sin(lat) - np.sin(self.p0) * np.cos(lat) * np.cos(dl)) * 6371)


class Frame:
    """Projection + conversion to viewBox coordinates."""

    def __init__(self, lon0, lat0, extent):
        self.P = LAEA(lon0, lat0)
        xs, ys = self.P([e[0] for e in extent], [e[1] for e in extent])
        self.x0, self.x1, self.y0, self.y1 = xs.min(), xs.max(), ys.min(), ys.max()
        self.k = W / (self.x1 - self.x0)
        self.H = round((self.y1 - self.y0) * self.k)

    def xy(self, lon, lat):
        x, y = self.P(lon, lat)
        return (x - self.x0) * self.k, (self.y1 - y) * self.k

    def pt(self, ll):
        x, y = self.xy(ll[0], ll[1])
        return [round(float(x), 1), round(float(y), 1)]


# ---------------------------------------------------------------- geometry
def polys(g):
    if g['type'] == 'Polygon':
        return [g['coordinates']]
    return g['coordinates'] if g['type'] == 'MultiPolygon' else []


def lines(g):
    if g['type'] == 'LineString':
        return [g['coordinates']]
    return g['coordinates'] if g['type'] == 'MultiLineString' else []


def simplify(a, tol):
    """Iterative Ramer–Douglas–Peucker."""
    if len(a) < 3:
        return a
    keep = np.zeros(len(a), bool)
    keep[0] = keep[-1] = True
    stack = [(0, len(a) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        p, q = a[i], a[j]
        seg = a[i + 1:j]
        d = q - p
        n = np.hypot(*d)
        if n == 0:
            dist = np.hypot(*(seg - p).T)
        else:
            dist = np.abs(d[0] * (seg[:, 1] - p[1]) - d[1] * (seg[:, 0] - p[0])) / n
        m = int(np.argmax(dist))
        if dist[m] > tol:
            k = i + 1 + m
            keep[k] = True
            stack += [(i, k), (k, j)]
    return a[keep]


def fmt(a):
    return 'M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in a)


def in_view(frame, a, pad=60):
    return not (a[:, 0].max() < -pad or a[:, 0].min() > W + pad
                or a[:, 1].max() < -pad or a[:, 1].min() > frame.H + pad)


def poly_d(frame, plist, tol=0.6, min_area=0):
    out = []
    for poly in plist:
        for ri, ring in enumerate(poly):
            r = np.array(ring)[:, :2]
            x, y = frame.xy(r[:, 0], r[:, 1])
            a = np.column_stack([x, y])
            if not in_view(frame, a):
                continue
            if ri == 0 and min_area:
                area = abs(np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])) / 2
                if area < min_area:
                    break
            a = simplify(a, tol)
            if len(a) >= 3:
                out.append(fmt(a) + 'Z')
    return ''.join(out)


def line_d(frame, lst, tol=0.5):
    out = []
    for ln in lst:
        r = np.array(ln)[:, :2]
        x, y = frame.xy(r[:, 0], r[:, 1])
        a = np.column_stack([x, y])
        if not in_view(frame, a):
            continue
        a = simplify(a, tol)
        if len(a) >= 2:
            out.append(fmt(a))
    return ''.join(out)


def ring_area(r):
    a = np.array(r)
    return abs(np.sum(a[:-1, 0] * a[1:, 1] - a[1:, 0] * a[:-1, 1])) / 2


def feat(lst, key, name):
    out = [p for f in lst if f['properties'].get(key) == name for p in polys(f['geometry'])]
    assert out, name
    return out


def region(n):
    return feat(REG, 'NAME', n)


def marine(n):
    return feat(MAR, 'name', n)


def lake(n):
    return feat(LAKES, 'name', n)


def country_main(n):
    return [max(feat(CTRY, 'NAME', n), key=lambda p: ring_area(p[0]))]


def river_lines(names):
    return [ln for f in RIVERS if f['properties'].get('name') in names for ln in lines(f['geometry'])]


def snap_to_lines(frame, lls, ll):
    """Point on the line (river) closest to the reference point."""
    best, bd = None, 1e18
    tx, ty = frame.xy(*ll)
    for ln in lls:
        r = np.array(ln)[:, :2]
        x, y = frame.xy(r[:, 0], r[:, 1])
        d = (x - tx) ** 2 + (y - ty) ** 2
        i = int(np.argmin(d))
        if d[i] < bd:
            bd, best = d[i], [round(float(x[i]), 1), round(float(y[i]), 1)]
    return best


# ---------------------------------------------------------------- base layer (blank map)
def base_layers(frame):
    land = ''.join(poly_d(frame, polys(f['geometry']), 0.6, 2) for f in LAND)
    plat = ''.join(poly_d(frame, polys(f['geometry']), 1.0, 20)
                   for f in REG if f['properties']['FEATURECLA'] == 'Plateau')
    mtn = ''.join(poly_d(frame, polys(f['geometry']), 1.0, 20)
                  for f in REG if f['properties']['FEATURECLA'] == 'Range/mtn')
    lakes = ''.join(poly_d(frame, polys(f['geometry']), 0.6, 4) for f in LAKES)
    minor = ''.join(line_d(frame, lines(f['geometry']), 0.8)
                    for f in RIVERS if f['properties'].get('scalerank', 9) <= 4)
    grat = []
    for lon in range(-180, 181, 10):
        la = np.linspace(-30, 85, 120)
        x, y = frame.xy(np.full_like(la, lon), la)
        a = np.column_stack([x, y])
        grat.append(fmt(simplify(a, 0.5)))
    for lat in range(-20, 90, 10):
        lo = np.linspace(-60, 250, 400)
        x, y = frame.xy(lo, np.full_like(lo, lat))
        a = np.column_stack([x, y])
        a = a[(a[:, 0] > -300) & (a[:, 0] < W + 300)]
        if len(a) > 1:
            grat.append(fmt(simplify(a, 0.5)))
    return {'graticule': ''.join(grat), 'land': land, 'plateaus': plat, 'mountains': mtn, 'lakes': lakes,
            'rivers': minor}


# ---------------------------------------------------------------- features
def build(frame, items):
    feats = []
    for it in items:
        fid, name, group, kind, src, dot, lab = it
        f = {'id': fid, 'name': name, 'group': group, 'kind': kind}
        if kind == 'area':
            f['d'] = poly_d(frame, src, 0.5)
            f['dot'] = frame.pt(dot)
        elif kind == 'river':
            lls = river_lines(src)
            f['d'] = line_d(frame, lls, 0.4)
            f['dot'] = snap_to_lines(frame, lls, dot)
        elif kind == 'line':  # strait
            a = np.array([frame.xy(*p) for p in src])
            f['d'] = fmt(a)
            f['dot'] = frame.pt(dot)
        elif kind == 'peak':
            f['dot'] = frame.pt(dot)
        f['label'] = frame.pt(lab) if lab else [f['dot'][0], round(f['dot'][1] - 22, 1)]
        feats.append(f)
    return feats


def europa():
    frame = Frame(18, 52, [(-26, 37), (63, 37), (-12, 72), (60, 72), (18, 32), (18, 72.5), (-26, 50), (66, 50)])
    med = sum((marine(n) for n in ['Mediterranean Sea', 'Tyrrhenian Sea', 'Adriatic Sea', 'Ionian Sea',
                                   'Aegean Sea', 'Balearic Sea', 'Golfe du Lion']), [])
    baltic = marine('Baltic Sea') + marine('Gulf of Bothnia') + marine('Gulf of Finland')
    if any(f['properties'].get('name') == 'Caspian Sea' for f in LAKES):
        caspi = lake('Caspian Sea')
    else:
        caspi = marine('Caspian Sea')
    items = [
        ('volga', 'Volga', 'Rius', 'river', {'Volga'}, (49.1, 55.8), (52.5, 55.3)),
        ('danubi', 'Danubi', 'Rius', 'river', {'Danube'}, (19.0, 47.3), (17.0, 45.4)),
        ('dnieper', 'Dnièper', 'Rius', 'river', {'Dnipro'}, (32.0, 49.0), (35.5, 50.6)),
        ('rin', 'Rin', 'Rius', 'river', {'Rhine'}, (7.4, 50.4), (4.4, 51.2)),
        ('caucas', 'Caucas', 'Serralades', 'area', region('CAUCASUS MTS.'), (44.0, 42.7), (45.0, 40.4)),
        ('pirineus', 'Pirineus', 'Serralades', 'area', region('PYRENEES'), (0.5, 42.7), (1.5, 44.4)),
        ('alps', 'Alps', 'Serralades', 'area', region('ALPS'), (10.5, 46.7), (12.0, 48.5)),
        ('urals', 'Urals', 'Serralades', 'area', region('URAL MOUNTAINS'), (59.3, 61.0), (54.5, 61.6)),
        ('balcans', 'Balcans', 'Serralades', 'area', region('Balkan Mts.'), (25.0, 42.75), (27.5, 41.4)),
        ('carpats', 'Càrpats', 'Serralades', 'area', region('CARPATHIAN MOUNTAINS') + region('Transylvanian Alps'),
         (25.0, 47.5), (28.0, 48.6)),
        ('mediterrani', 'Mar Mediterrani', 'Mars', 'area', med, (18.5, 35.3), (18.5, 33.9)),
        ('negre', 'Mar Negre', 'Mars', 'area', marine('Black Sea'), (34.0, 43.3), (34.5, 44.6)),
        ('caspi', 'Mar Caspi', 'Mars', 'area', caspi, (51.0, 42.3), (53.5, 44.6)),
        ('baltic', 'Mar Bàltic', 'Mars', 'area', baltic, (19.5, 55.8), (16.0, 57.8)),
        ('nord', 'Mar del Nord', 'Mars', 'area', marine('North Sea'), (3.0, 56.0), (2.5, 57.6)),
        ('iberica', 'Península Ibèrica', 'Penínsules', 'area', country_main('Spain') + country_main('Portugal'),
         (-4.0, 40.0), (-4.5, 38.6)),
        ('italica', 'Península Itàlica', 'Penínsules', 'area', country_main('Italy'), (15.3, 40.9), (17.6, 42.5)),
        ('balcanica', 'Península Balcànica', 'Penínsules', 'area', region('BALKAN PEN.'), (21.6, 41.0),
         (21.5, 39.4)),
        ('escandinava', 'Península Escandinava', 'Penínsules', 'area', region('SCANDINAVIA'), (15.0, 63.5),
         (16.0, 65.2)),
        ('balears', 'Illes Balears', 'Illes', 'area', region('Balearic Islands'), (2.9, 39.6), (4.2, 37.9)),
        ('britaniques', 'Illes Britàniques', 'Illes', 'area', region('BRITISH ISLES'), (-1.8, 53.0),
         (-9.5, 57.6)),
        ('islandia', 'Islàndia', 'Illes', 'area', region('ICELAND'), (-18.5, 64.9), (-18.5, 63.3)),
        ('corsega', 'Còrsega', 'Illes', 'area', region('Corse'), (9.1, 42.15), (6.8, 43.1)),
        ('sicilia', 'Sicília', 'Illes', 'area', region('Sicilia'), (14.2, 37.5), (12.6, 36.4)),
        ('sardenya', 'Sardenya', 'Illes', 'area', region('Sardegna'), (9.0, 40.0), (5.6, 41.0)),
        ('planura', 'Gran Planura centreeuropea', 'Planes', 'area', region('NORTHERN EUROPEAN PLAIN'),
         (20.0, 52.5), (21.0, 54.0)),
    ]
    return frame, items


def asia():
    frame = Frame(100, 40, [(28, 32), (-165, 66), (100, 79), (100, -11), (30, 12), (150, -8), (60, 70), (-172, 55)])
    items = [
        ('tigris', 'Tigris', 'Rius', 'river', {'Tigris'}, (44.4, 33.6), (49.0, 35.8)),
        ('eufrates', 'Èufrates', 'Rius', 'river', {'Euphrates'}, (40.5, 34.6), (36.0, 31.8)),
        ('iangtse', 'Iangtsé', 'Rius', 'river', {'Yangtze', 'Chang Jiang'}, (112.0, 30.3), (113.5, 26.8)),
        ('indus', 'Indus', 'Rius', 'river', {'Indus'}, (71.0, 29.0), (66.0, 30.2)),
        ('ganges', 'Ganges', 'Rius', 'river', {'Ganges'}, (83.0, 25.4), (85.0, 23.2)),
        ('mekong', 'Mekong', 'Rius', 'river', {'Mekong'}, (105.9, 14.5), (110.0, 13.2)),
        ('himalaia', 'Himàlaia', 'Serralades', 'area', region('HIMALAYAS'), (82.0, 30.0), (88.0, 32.6)),
        ('everest', 'Everest (8.848 m)', 'Serralades', 'peak', None, (86.925, 27.988), (82.0, 25.2)),
        ('roig', 'Mar Roig', 'Mars', 'area', marine('Red Sea'), (38.8, 19.6), (34.0, 26.0)),
        ('baikal', 'Llac Baikal', 'Llacs', 'area', lake('Lake Baikal'), (108.2, 53.4), (114.5, 57.3)),
        ('gobi', 'Desert del Gobi', 'Deserts', 'area', region('GOBI DESERT'), (105.0, 43.0), (105.0, 45.6)),
        ('arabia_desert', "Desert d'Aràbia", 'Deserts', 'area', region('RUB’ AL KHALI'), (50.0, 20.0),
         (51.5, 17.0)),
        ('arabiga', 'Península Aràbiga', 'Penínsules', 'area', region('ARABIAN PENINSULA'), (44.0, 25.0),
         (41.5, 28.2)),
        ('india', "Península de l'Índia (Indostan)", 'Penínsules', 'area', region('INDIA'), (77.5, 17.5),
         (73.5, 13.0)),
        ('indoxina', "Península d'Indoxina", 'Penínsules', 'area', region('INDOCHINA PENINSULA'), (101.0, 17.0),
         (99.0, 20.2)),
        ('corea', 'Península de Corea', 'Penínsules', 'area', region('KOREA'), (127.6, 37.3), (133.5, 41.0)),
        ('srilanka', 'Sri Lanka', 'Illes', 'area', region('SRI LANKA'), (80.7, 7.8), (85.0, 5.6)),
        ('sumatra', 'Sumatra', 'Illes', 'area', region('SUMATRA'), (101.0, -0.5), (96.0, -3.8)),
        ('borneo', 'Borneo', 'Illes', 'area', region('BORNEO'), (114.0, 1.0), (114.0, 4.2)),
        ('bering', 'Estret de Bering', 'Estrets', 'line', [(-169.7, 66.08), (-168.1, 65.6)], (-168.9, 65.85),
         (-176.0, 62.8)),
        ('bengala', 'Golf de Bengala', 'Golfs', 'area', marine('Bay of Bengal'), (89.0, 15.5), (89.0, 13.4)),
        ('persic', 'Golf Pèrsic', 'Golfs', 'area', marine('Persian Gulf'), (51.5, 27.2), (57.5, 30.6)),
        ('filipines', 'Les Filipines', 'Arxipèlegs', 'area', region('PHILIPPINES'), (122.5, 12.5), (129.5, 13.8)),
        ('japo', 'Japó', 'Arxipèlegs', 'area', region('JAPAN'), (139.0, 36.5), (145.0, 40.0)),
    ]
    return frame, items


def write(key, title, frame, items):
    data = {'id': key, 'title': title, 'viewBox': [0, 0, W, frame.H],
            'base': base_layers(frame), 'features': build(frame, items)}
    os.makedirs(OUT, exist_ok=True)
    # Saved as a script (not JSON) so the page also works when opening index.html without a server.
    p = os.path.join(OUT, key + '.js')
    with open(p, 'w', encoding='utf-8') as fh:
        fh.write('// Generated by tools/generate_maps.py — do not edit by hand.\n')
        fh.write('window.MAP_DATA = window.MAP_DATA || {};\n')
        fh.write(f'window.MAP_DATA[{json.dumps(key)}] = ')
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    print(p, round(os.path.getsize(p) / 1024), 'KB', len(items), 'accidents')


if __name__ == '__main__':
    write('europa', 'Europa', *europa())
    write('asia', 'Àsia', *asia())
