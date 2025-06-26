========
Concepts
========

Vessim helps you to understand and optimize how your (distributed) computing system interacts with (distributed) renewable energy sources and battery storage.


What You Can Do With Vessim
============================

**Test Carbon-Aware Applications**
    Develop applications that automatically reduce their energy consumption when the grid is powered by fossil fuels, and increase activity when renewable energy is abundant.

**Optimize Data Center Energy Mix**
    Experiment with adding solar panels, wind turbines, or batteries to see how they would affect your energy costs and carbon emissions.

**Plan for Outages and Extreme Events**
    Simulate power outages or renewable energy fluctuations to understand risks and test backup strategies.

**Validate Software Changes**
    Test how new software deployments or configuration changes will affect energy consumption before rolling them out.

How Vessim Works
================

Vessim creates virtual "microgrids" - small energy systems that combine computing equipment with renewable energy sources and batteries. You can run multiple scenarios in parallel and see results faster than real-time.

.. image:: _static/vessim_co-simulation_concept.png
    :width: 100%
    :alt: Vessim Co-Simulation Concept

**Actors: Energy Consumers and Producers**
    - Computing systems (servers, workstations, etc.) that consume power
    - Renewable sources (solar panels, wind turbines) that produce power
    - Both can use real historical data or custom patterns

**Energy Storage**
    - Batteries that store excess renewable energy for later use
    - Configurable charging/discharging policies based on your strategy

**Controllers: Enable Monitoring, Web APIs, and Custom Policies**
    - Track energy flows, carbon emissions, and costs over time
    - Export data for analysis or integrate with real systems via APIs
    - Control when computing workloads run based on energy availability

**Real-World Integration**
    - Connect real applications to simulated energy systems
    - Test how your software responds to changing energy conditions
    - Validate carbon-aware algorithms before deployment

For examples, please refer to our tutorials.


Working with Historical Data
============================

Vessim includes ready-to-use historical datasets for common scenarios:

**Carbon Intensity Data**
    Real historical data showing how "clean" or "dirty" the electricity grid was at different times and locations.

**Solar and Wind Production**
    Historical weather data converted to realistic power generation patterns for renewable energy sources.

**Custom Data Sources**
    Import your own historical data for power consumption, production, or any other time-series information you want to simulate.

This historical data drives your simulations, so you can see how your systems would have performed under real-world conditions. You can also create custom patterns or use the data to predict future scenarios.
