========
Datasets
========
Vessim comes with several datasets that can be directly used inside simulations through our :class:`HistoricalSignal <vessim.signal.HistoricalSignal>`.

----

.. image:: _static/solcast_logo.png
   :height: 3em
   :alt: Solcast

`Solcast <https://solcast.com>`_ provides solar resource assessment and forecasting data for irradiance and PV power.

solcast2022_global
==================
    Dataset containing actual historical data and historical forcasts of solar irradiance in different international cities between the 8th of June and 6th of July 2022.

    .. rst-class:: labeled-list

    - **Unit:** Fraction of maximum possible solar output normalized between 0 and 1 (can be scaled linearly with the output of the solar plant)
    - **Zones:** Berlin, Cape Town, Hong Kong, Lagos, Mexico City, Mumbai, San Francisco, Stockholm, Sydney, São Paulo 

    **Actual data:**
        .. rst-class:: labeled-list

        - **Interval:** 5 Minutes
        - **Fill-Method:** Backward-Fill (value is always valid for the 5 minutes before the timestamp)
        - **Size:** 712kB (8353 rows, 11 columns)
    **Forecast data:**
        .. rst-class:: labeled-list

        - **Request-Interval:** 5 Minutes (every 5 minutes a new forecast is available for the next 65 minutes so that there is at least one hour of forecasts available at all times)
        - **Forecast-Interval:** 5 Minutes 
        - **Size:** 10.9 MB (107342 rows, 12 columns)

    .. raw:: html

        <iframe src="_static/solcast2022_global_plot.html" style="width: 100%; height: 30vh;"></iframe>

solcast2022_germany
===================
    Dataset containing actual historical data and historical forcasts of solar irradiance in different cities in Germany between the 15th of July and 14th of August 2022.

    .. rst-class:: labeled-list

    - **Unit:** Fraction of maximum possible solar output normalized between 0 and 1 (can be scaled linearly with the output of the solar plant)
    - **Zones:** Berlin, Cologne, Dortmund, Düsseldorf, Essen, Frankfurt, Hamburg, Leipzig, Munich, Stuttgart

    **Actual data:**
        .. rst-class:: labeled-list

        - **Interval:** 5 Minutes
        - **Fill-Method:** Backward-Fill (value is always valid for the 5 minutes before the timestamp)
        - **Size:** 798kB (8929 rows, 11 columns)
    **Forecast data:**
        .. rst-class:: labeled-list

        - **Request-Interval:** 5 Minutes (every 5 minutes a new forecast is available for the next 65 minutes so that there is at least one hour of forecasts available at all times)
        - **Forecast-Interval:** 5 Minutes 
        - **Size:** 12.1 MB (114830 rows, 12 columns)

    .. raw:: html

        <iframe src="_static/solcast2022_germany_plot.html" style="width: 100%; height: 30vh;"></iframe>

----

.. image:: _static/watttime_logo.png
   :height: 3em
   :alt: Watttime

`Wattime <https://watttime.org/>`_ is a non-profit organization, providing electricity grid-related data like the Marginal Operating Emissions Rate (MOER), representing the emissions rate of the electricity generator(s) that are responding to changes in load on the local grid at a certain time. 

watttime2023_caiso-north
========================
    Dataset containing actual historical data and historical forecasts of the MOER in the caiso-North region between the 8th of June and the 8th of July 2023. The original data is provided in lbs/MWh, but in the dataset, it is converted to g/kWh.

    **Actual data:**
        .. rst-class:: labeled-list

        - **Unit:** g/kWh
        - **Interval:** 5 Minutes
        - **Fill-Method:** Forward-Fill (value is always valid for the next 5 minutes after the timestamp)
        - **Size:** 357kB (8929 rows, 2 columns)
    **Forecast data:**
        .. rst-class:: labeled-list

        - **Unit:** g/kWh
        - **Request-Interval:** 5 Minutes (every 5 minutes a new forecast is available for the next 65 minutes so that there is at least one hour of forecasts available at all times)
        - **Forecast-Interval:** 5 Minutes 
        - **Size:** 7.5 MB (115933 rows, 3 columns)

    .. raw:: html

        <iframe src="_static/watttime2023_caiso-north_plot.html" style="width: 100%; height: 30vh;"></iframe>