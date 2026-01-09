# central-data-api

## Project structure
```
vessim-central-data-api/
├── main.py                      # Haupt-App, sammelt alle Router
├── core/
│   ├── database.py              # Gemeinsame DB-Engine & Basis-Modelle
│   └── config.py                # Konfiguration
├── plugins/                     # Hier leben alle Plugins
│   ├── __init__.py
│   ├── entsoe/                  # ENTSO-E Plugin
│   │   ├── __init__.py
│   │   ├── models.py            # Eigene ENTSO-E-Tabellen
│   │   ├── api.py               # Eigene API-Endpunkte (/entsoe/...)
│   │   └── service.py           # Geschäftslogik & Abruf von entso-e.de
│   ├── solcast/                 # Solar-Daten Plugin
│   │   ├── __init__.py
│   │   ├── models.py
│   │   └── api.py
│   └── plugin_registry.py       # Zentrale Registrierung aller Plugins
└── requirements.txt
```


## Start

```
python main.py
```