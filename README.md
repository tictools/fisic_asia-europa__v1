# Mapes físics · Europa i Àsia (v1)

Activitat interactiva per situar accidents geogràfics en un mapa mut. Cal arrossegar cada nom fins al seu punt del mapa:

- **Si encertes**, el nom desapareix de la safata i la zona o el riu es ressalta al mapa amb el color del grup i el nom.
- **Si falles**, el nom torna al seu lloc i es compta un error.

Funciona en **ordinador i tauleta**. En un mòbil mostra un avís perquè la pantalla és massa petita per a l'activitat.

## Estructura

```
index.html          Pàgina única: inici (Europa | Àsia), activitat i avisos
css/styles.css      Estils i colors dels grups (variables CSS al principi)
js/app.js           Lògica: navegació (#/europa, #/asia), mapa SVG, arrossegar i deixar anar
data/europa.js      Mapa mut + accidents d'Europa (generat)
data/asia.js        Mapa mut + accidents d'Àsia (generat)
tools/generate_maps.py   Script que genera data/*.js a partir de Natural Earth
```

És HTML, CSS i JavaScript sense dependències ni pas de compilació. L'arrossegament utilitza Pointer Events, que funcionen amb ratolí i amb pantalla tàctil.

## Provar-ho en local

Obre `index.html` directament al navegador, o bé:

```bash
npx serve .          # o: python3 -m http.server 8000
```

## Canviar accidents o enquadrament

Els accidents de cada mapa (nom, grup, punt i posició de l'etiqueta) estan definits a `tools/generate_maps.py`, a les funcions `europa()` i `asia()`. Per regenerar les dades:

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/nvkelso/natural-earth-vector tools/natural-earth-vector
cd tools/natural-earth-vector && git sparse-checkout set --no-cone '/geojson/ne_50m_land.geojson' \
  '/geojson/ne_50m_lakes.geojson' '/geojson/ne_10m_rivers_lake_centerlines.geojson' \
  '/geojson/ne_10m_geography_regions_polys.geojson' '/geojson/ne_50m_geography_marine_polys.geojson' \
  '/geojson/ne_50m_admin_0_countries.geojson' && cd ../..
python3 tools/generate_maps.py     # requereix numpy
```

## Colors dels grups

| Grup | Color | Distintiu |
|---|---|---|
| Rius | blau `#1E6FE0` | recorregut ressaltat |
| Serralades | vermell `#C62828` | trama de triangles |
| Mars | turquesa `#00A5B5` | vora de punts |
| Penínsules | morat `#7B1FA2` | vora discontínua |
| Illes | verd `#2E7D32` | |
| Planes | groc `#D9A300` | |
| Llacs | blau marí `#1A237E` | |
| Deserts | taronja `#EF6C00` | |
| Estrets | negre `#111111` | |
| Golfs | rosa `#E8558A` | vora de punts |
| Arxipèlegs | marró `#795548` | |

Dades cartogràfiques: [Natural Earth](https://www.naturalearthdata.com/) (domini públic).
