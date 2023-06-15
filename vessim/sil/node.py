class Node:
    """Represents a physical or virtual computing node.

    This class keeps track of nodes and assigns unique IDs to each new instance. It also
    allows the setting of a power meter and power mode.

    Args:
        address: The network address of the node.
        power_mode: The power mode of the node. Default is "high performance".

    Attributes:
        id: A unique ID assigned to each node. The ID is auto-incremented for
            each new node.
        address: The network address of the node.
        power_mode: The power mode of the node. Default is "high performance".
    """

    # keep track of ids
    id = 0

    def __init__(
        self,
        address: str,
        port: int = 8000,
        power_mode: str = "high performance"
    ) -> None:
        Node.id += 1
        self.id = Node.id
        self.address = address
        self.port = port
        self.power_mode = power_mode
