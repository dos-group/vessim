class LinearPowerModel:
    """Class for implementing a linear power model.

    Attributes:
        p_static: The static power component.
        p_max: The maximum power component.
    """

    def __init__(self, p_static, p_max):
        self.p_static = p_static
        self.p_max = p_max


    def __call__(self, utilization: float) -> float:
        """Compute power based on utilization.

        Args:
            utilization: A float representing current utilization.

        Returns:
            Power value as a float based on utilization.
        """
        return self.p_static + utilization * (self.p_max - self.p_static)
