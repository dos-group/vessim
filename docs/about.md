# About Vessim

Most research on energy-aware and carbon-aware computing relies on simulations, as globally distributed hardware testbeds are rare and costly.
Vessim addresses this gap by simplifying and unifying simulation-based evaluations and enabling continuous testing of emerging applications.

Vessim is developed by [Philipp Wiesner](https://philippwiesner.org) at the [Distributed and Operating Systems (DOS)](https://www.dos.tu-berlin.de) group at TU Berlin.
Active development for Vessim began in March 2023 with initial funding from the [German Federal Ministry of Education and Research (BMBF)](https://www.bmbf.de/) as part of the Software Campus project [SYNERGY](https://softwarecampus.de/en/projekt/synergy-synergies-of-distributed-artificial-intelligence-and-renewable-energy-generation/).
We thank everyone who has contributed to Vessim over the past years, especially Marvin Steinke, Paul Kilian, and Amanda Malkowski.

## Roadmap

We are currently working on the following aspects and features:

- **Improved SiL capabilities**: We are woking on smoother integration of real hardware testbeds into Vessim's software-in-the-loop simulation methodology.
- **System Advisor Model (SAM)**: We are working on integrating NREL's [SAM](https://sam.nrel.gov/) as a subsystem in Vessim, allowing for better simulation of solar arrays, wind farms, and other types of renewable energy generators.
- **Battery degradation**: We are working on integrating NREL's [BLAST-Lite](https://github.com/NREL/BLAST-Lite) for modeling battery lifetime and degradation
- **Calibration**: We are working on a methodology for calibrating Vessim simulations on real hardware testbeds.

## License

Vessim is released under the [MIT License](https://github.com/dos-group/vessim/blob/main/LICENSE).
