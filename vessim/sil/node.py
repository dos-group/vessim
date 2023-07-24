from typing import Set

class Node:
    """Represents a physical or virtual computing node.

    This class keeps track of nodes and assigns unique IDs to each new
    instance. It also allows the setting of a power meter and power mode.

    Args:
        id: A unique ID assigned to each node.
        address: The network address of the node.
        port: The application port of the node api.
        power_mode: The power mode of the node. Default is "high performance".
    """

    existing_ids: Set[str] = set()

    def __init__(
        self,
        id: str,
        address: str,
        port: int = 8000,
        power_mode: str = "high performance"
    ) -> None:
        if id in self.existing_ids:
            raise ValueError(f"Node ID \"{id}\" already exists.")
        self.existing_ids.add(id)
        self.id = id
        self.address = address
        self.port = port
        self.power_mode = power_mode
