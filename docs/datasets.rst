========
Datasets
========
Vessim comes with several built-in datasets that can be easily loaded and used inside a simulations.

Watttime
========
Wattime is a non-profit organization, providing electricity grid-related data like the Marginal Operating Emissions Rate (MOER), representing the emissions rate of the electricity generator(s) that are responding to changes in load on the local grid at a certain time. 

**'watttime2023_casio-north':**
    Dataset containing actual historical data and historical forecasts of the MOER in the Casio-North region between the 8th of June and the 8th of July 2023. The original data is provided in lbs/MWh, but in the dataset, it is converted to g/kWh.

    **Actual data:**
        .. rst-class:: labeled-list

        - **Unit:** g/kWh
        - **Interval:** 5 Minutes
        - **Fill-Method:** Forward-Fill (value is always valid for the next 5 minutes after the timestamp)
        - **Filename:** "watttime2023_casio-north_actual.csv"
        - **Size:** 357kB (8929 rows, 2 columns)
    **Forecast data:**
        .. rst-class:: labeled-list

        - **Unit:** g/kWh
        - **Request-Interval:** 5 Minutes (every 5 minutes a new forecast is available for the next 65 minutes so that there is one hour of forecast available everytime)
        - **Forecast-Interval:** 5 Minutes 
        - **Filename:** "watttime2023_casio-north_forecast.csv"
        - **Size:** 7.5 MB (115933 rows, 3 columns)

.. raw:: html

    <iframe src="_static/watttime2023_casio-north_plot.html" style="width: 100%; height: 50vh;"></iframe>

Solcast
=======
Solcast operates as a DNV company, providing solar resource assessment and forecasting data for irradiance and PV power.

**'solcast2022_germany'**
    Dataset containing actual historical data and historical forcasts of solar irradiance in different german cities between the 15th of July and 14th of August 2022.

    **Actual data:**
        .. rst-class:: labeled-list

        - **Zones:** Berlin, Cologne, Dortmund, Düsseldorf, Essen, Frankfurt, Hamburg, Leipzig, Munich, Stuttgart
        - **Interval:** 5 Minutes
        - **Fill-Method:** Backward-Fill (value is always valid for the 5 minutes before the timestamp)
        - **Filename:** "solcast2022_germany_actual.csv"
        - **Size:** 798kB (8929 rows, 11 columns)
    **Forecast data:**
        .. rst-class:: labeled-list

        - **Zones:** Berlin, Cologne, Dortmund, Düsseldorf, Essen, Frankfurt, Hamburg, Leipzig, Munich, Stuttgart
        - **Request-Interval:** 5 Minutes (every 5 minutes a new forecast is available for the next 65 minutes so that there is one hour of forecast available everytime)
        - **Forecast-Interval:** 5 Minutes 
        - **Filename:** "solcast2022_germany_forecast.csv"
        - **Size:** 12.1 MB (114830 rows, 12 columns)

    .. raw:: html

        <iframe src="_static/solcast2022_germany_plot.html" style="width: 100%; height: 50vh;"></iframe>

**'solcast2022_global'**
    Dataset containing actual historical data and historical forcasts of solar irradiance in different international cities between the 8th of June and 6th of July 2022.

    **Actual data:**
        .. rst-class:: labeled-list

        - **Zones:** Berlin, Cape Town, Hong Kong, Lagos, Mexico City, Mumbai, San Francisco, Stockholm, Sydney, São Paulo 
        - **Interval:** 5 Minutes
        - **Fill-Method:** Backward-Fill (value is always valid for the 5 minutes before the timestamp)
        - **Filename:** "solcast2022_global_actual.csv"
        - **Size:** 712kB (8353 rows, 11 columns)
    **Forecast data:**
        .. rst-class:: labeled-list

        - **Zones:** Berlin, Cape Town, Hong Kong, Lagos, Mexico City, Mumbai, San Francisco, Stockholm, Sydney, São Paulo 
        - **Request-Interval:** 5 Minutes (every 5 minutes a new forecast is available for the next 65 minutes so that there is one hour of forecast available everytime)
        - **Forecast-Interval:** 5 Minutes 
        - **Filename:** "solcast2022_global_forecast.csv"
        - **Size:** 10.9 MB (107342 rows, 12 columns)

    .. raw:: html

        <iframe src="_static/solcast2022_global_plot.html" style="width: 100%; height: 50vh;"></iframe>