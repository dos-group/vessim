import collections
import csv
from loguru import logger

import mosaik_api


META = {
    "type": "event-based",
    "models": {
        "Monitor": {
            "public": True,
            "any_inputs": True,
            "params": [],
            "attrs": [],
        },
    },
}


class Collector(mosaik_api.Simulator):
    """Simple data collector for printing data at the end of simulation.

    Attributes:
        eid: Identifier of Simulator Instance
        data: Dictionary for holding the necessary simulation data
    """

    def __init__(self):
        super().__init__(META)
        self.eid = None
        self.data = collections.defaultdict(lambda: collections.defaultdict(dict))

    def init(self, sid, time_resolution):
        """Initializes the simulator instance.

        Returns:
            dict: Simulator metadata.
        """
        return self.meta

    def create(self, num, model):
        """Creates the collector instance.

        Args:
            num (int): Number of instances to create (1 allowed).
            model (str): Model type.

        Returns:
            list: List containing the instance description.

        Raises:
            RuntimeError: When creating more than one Collector instance.
        """
        if num > 1 or self.eid is not None:
            raise RuntimeError("Can only create one instance of Monitor.")

        self.eid = "Monitor"
        return [{"eid": self.eid, "type": model}]

    def step(self, time, inputs, max_advance):
        """Logging and saving of data from current step.

        Executed every simulation step.

        Args:
            time (float): Current simulation time.
            inputs (dict): Dictionary containing input data.
            max_advance (float): Maximum time to advance in this step.

        Returns:
            None: Indicates no further time advancement.
        """
        data = inputs.get(self.eid, {})
        logger.info(f"# {str(time):>5} ----------")
        for attr, values in data.items():
            for src, value in values.items():
                logger.info(f"{src}[{attr}] = {value}")
                self.data[src][attr][time] = value
        return None

    def finalize(self):
        """Collected data is printed to file at simulation end."""
        print("Collected data:")
        for _, sim_data in sorted(self.data.items()):
            table = []
            for attr, values in sorted(sim_data.items()):
                row = [attr]
                for value in values.values():
                    row.append(f"{value:3.2f}")
                table.append(row)
            end = list(list(sim_data.values())[0].keys())[-1] + 1
            time_column = [str(i) for i in list(range(end))]
            time_column.insert(0, "time")
            csv_data = [time_column] + table
            with open("data.csv", "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(zip(*csv_data))
