# central-data-api

## Project structure
```
data/
├── main.py                      # main-app, collects als routers from plugins
├── core/
│   ├── database.py              # joined db-engine & base-models
│   └── config.py                # configuration
├── plugins/                     # plugin
│   ├── __init__.py
│   ├── entsoe/                  # entso-e plugin
│   │   ├── __init__.py          # defines plugin-specific router, models and startup for cennecting to main.py
│   │   ├── models.py            # plugin-specific tables for db
│   │   ├── api.py               # plugin-specific api endpoints
│   │   ├── entsoe_service.py    # main logic
|   |   └── requierements.txt    # plugin-specific requierements
└── requirements.txt
```


## Start

```
python main.py
```