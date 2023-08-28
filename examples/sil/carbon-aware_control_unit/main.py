import argparse
from cacu import CarbonAwareControlUnit


def argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--node_ids",
        help="ids of nodes",
        nargs="+",
        action="append",
        required=True
    )
    parser.add_argument(
        "--server_address",
        help="address of the API server",
        default="http://127.0.0.1:8000"
    )
    parser.add_argument(
        "--step_size",
        help="Simulation step size.",
        default=60
    )
    parser.add_argument(
        "--rt_factor",
        help="""real time factor of the simulation e.g rt_factor=1/60 means the
        cacu run 60x faster as wall clock time""",
        default=1/60
    )
    parser.add_argument(
        "--update_interval",
        help="""update interval of the getter methods. defaults to
        rt_factor""",
        default=None
    )

    return parser


if __name__ == "__main__":
    parser = argparser()
    args = parser.parse_args()
    cacu = CarbonAwareControlUnit(args.server_address, args.node_ids[0])
    cacu.run_scenario(args.rt_factor, args.step_size, args.update_interval)
