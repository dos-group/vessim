# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vessim is a co-simulation testbed for carbon-aware applications and systems. It connects domain-specific simulators for renewable power generation and energy storage with real software and hardware using the Mosaik co-simulation framework.

## Development Commands

### Environment Setup
```bash
# Install with development dependencies
uv pip install -e ".[dev,docs,sil,examples,vis]"
```

### Code Quality
```bash
# Type checking
uv run mypy vessim

# Linting 
uv run ruff check vessim

# Auto-fix linting issues
uv run ruff check --fix vessim

# Code formatting
uv run black vessim

# Run all tests
uv run pytest
```

### Documentation
```bash
# Build documentation locally
cd docs
make html
# Open _build/html/index.html in browser

# Clean documentation build
rm -rf _build && make html
```

## Architecture Overview

Vessim is built around a co-simulation architecture using Mosaik. The core components are:

### Core Simulation Components
- **Environment** (`cosim.py`): Main simulation orchestrator that manages microgrids and runs simulations
- **Microgrid** (`cosim.py`): Represents a single microgrid with actors, controllers, storage, and policies
- **Actor** (`actor.py`): Base class for power consumers/producers (solar panels, computing systems, etc.)
- **Signal** (`signal.py`): Time-series data sources (historical data, real-time feeds, mock data)
- **Storage** (`storage.py`): Battery and energy storage models
- **Controller** (`controller.py`): Components that monitor and control microgrids
- **Policy** (`policy.py`): Decision-making logic for microgrid management

### Key Actor Types
- **Actor**: Generic power consumer/producer based on a Signal
- **StaticSignal**: Simple signal with constant values for testing
- **Trace**: Time-series data from datasets (solar, carbon intensity)

### Software-in-the-Loop (SiL)
Optional SiL capabilities (`sil.py`) enable real-time interaction with external systems:
- **Broker**: Manages communication between simulation and external systems
- **SilController**: Controller for SiL scenarios
- **WatttimeSignal**: Real-time carbon intensity data from WattTime

### Data Management
- **Datasets**: Pre-loaded solar irradiance and carbon intensity data from Solcast and WattTime
- **_data.py**: Dataset loading and management utilities
- **_util.py**: Common utilities including Clock and datetime handling

## Testing

Tests are located in the `tests/` directory and cover:
- Consumer/producer behavior (`test_consumer.py`)
- Signal functionality (`test_signal.py`) 
- Storage systems (`test_storage.py`)

The CI pipeline runs tests on Python 3.9 and 3.13.

## Code Style

- Line length: 99 characters (configured in pyproject.toml)
- Uses Black for formatting and Ruff for linting
- Google-style docstrings enforced by Ruff
- Type hints required (checked with mypy)
- Some docstring requirements disabled for now (D100, D101, D102, D103, D107)

## Example Usage Pattern

```python
import vessim as vs

# Create environment
environment = vs.Environment(sim_start="2022-06-15")

# Add microgrid with actors, controllers, and storage
environment.add_microgrid(
    actors=[
        vs.Actor(name="server", signal=vs.StaticSignal(value=-400)),
        vs.Actor(name="solar_panel", signal=vs.Trace.load("solcast2022_global", column="Berlin"))
    ],
    controllers=[vs.Monitor(outfile="result.csv")],
    storage=vs.SimpleBattery(capacity=100),
    step_size=60,
)

# Run simulation
environment.run(until=24 * 3600)  # 24 hours
```

## Important Notes

- The project uses Mosaik for co-simulation orchestration
- All datetime handling goes through the Clock utility in `_util.py`
- Actors must implement the `p(now)` method returning current power consumption/production
- Step sizes must be multiples of the microgrid's step size
- SiL features require additional dependencies and are optional

## Development Guidelines

- **Minimal error handling**: Avoid excessive try-catch blocks and error handling unless explicitly requested. Let exceptions bubble up naturally.
- **Keep it simple**: Don't add unnecessary complexity or defensive programming patterns unless specifically asked.