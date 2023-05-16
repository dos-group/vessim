import mosaik_api
from simulator.single_model_simulator import SingleModelSimulator

META = {
    'type': 'event-based',
    'models': {
        'CarbonAgent': {
            'public': True,
            'params': ['carbon_conversion_factor'],
            'attrs': ['ci'],
        },
    },
}


class CarbonController(SingleModelSimulator):
    """Carbon Controller.

    Acts as a medium between carbon module and ecovisor or direct consumer since
    producer is only a CSV generator.
    """

    def __init__(self):
        super().__init__(META, CarbonAgent)


class CarbonAgent:
    """Class to represent the Carbon Agent.

        Args:
            unit: the unit of measurement for carbon intensity. Default is
            'g_per_kWh'. Supported units are:
                - 'g_per_kWh': grams of CO2 emitted per kilowatt hour of
                  electricity produced.
                - 'lb_per_MWh': pounds of CO2 emitted per megawatt hour of
                  electricity produced.

        Raises:
            ValueError: If the provided unit is not one of the supported units.

        Attributes:
            carbon_conversion_factor: the conversion factor used to calculate
            carbon intensity based on the unit of measurement.
            ci: the grid carbon intensity
        """

    def __init__(self, unit: str ='g_per_kWh') -> None:
        if unit == 'g_per_kWh':
            # standard unit used in vessim
            self.carbon_conversion_factor = 1
        elif unit == 'lb_per_MWh':
            self.carbon_conversion_factor = 0.45359237
        else:
            raise ValueError(f'{unit} is not supported by vessim')
        self.ci = 0.0

    def step(self, ci: float) -> None:
        """Calculate the carbon intensity based on the input intensity and the
        conversion factor. Called every simulation step.
        """
        self.ci = abs(ci * self.carbon_conversion_factor)
