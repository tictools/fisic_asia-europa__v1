# Physical maps · Europe and Asia (v1)

An interactive activity for placing geographical features on a blank map. Drag each name to its position on the map:

- **If you get it right**, the name disappears from the tray and the area or river is highlighted on the map in its group colour, together with its name.
- **If you get it wrong**, the name returns to its place and an error is counted.

It works on **computers and tablets**. On a mobile phone it shows a notice, as the screen is too small for the activity.

## Structure

```
index.html          Single page: start screen (Europe | Asia), activity and notices
css/styles.css      Styles and group colours (CSS variables at the top)
js/app.js           Logic: navigation (#/europa, #/asia), SVG map, drag and drop
data/europa.js      Blank map + features of Europe (generated)
data/asia.js        Blank map + features of Asia (generated)
tools/generate_maps.py   Script that generates data/*.js from Natural Earth
```

It is plain HTML, CSS and JavaScript with no dependencies or build step. Dragging uses Pointer Events, which work with both mouse and touchscreen.

## Running locally

Open `index.html` directly in the browser, or:

```bash
npx serve .          # or: python3 -m http.server 8000
```

## Changing features or map framing

The features of each map (name, group, point and label position) are defined in `tools/generate_maps.py`, in the `europa()` and `asia()` functions. To regenerate the data:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/nvkelso/natural-earth-vector tools/natural-earth-vector
cd tools/natural-earth-vector && git sparse-checkout set --no-cone '/geojson/ne_50m_land.geojson' \
  '/geojson/ne_50m_lakes.geojson' '/geojson/ne_10m_rivers_lake_centerlines.geojson' \
  '/geojson/ne_10m_geography_regions_polys.geojson' '/geojson/ne_50m_geography_marine_polys.geojson' \
  '/geojson/ne_50m_admin_0_countries.geojson' && cd ../..
python3 tools/generate_maps.py     # requires numpy
```

## Group colours

| Group | Colour | Distinguishing mark |
|---|---|---|
| Rivers | blue `#1E6FE0` | highlighted course |
| Mountain ranges | red `#C62828` | triangle pattern |
| Seas | turquoise `#00A5B5` | dotted edge |
| Peninsulas | purple `#7B1FA2` | dashed edge |
| Islands | green `#2E7D32` | |
| Plains | yellow `#D9A300` | |
| Lakes | navy blue `#1A237E` | |
| Deserts | orange `#EF6C00` | |
| Straits | black `#111111` | |
| Gulfs | pink `#E8558A` | dotted edge |
| Archipelagos | brown `#795548` | |

Cartographic data: [Natural Earth](https://www.naturalearthdata.com/) (public domain).
