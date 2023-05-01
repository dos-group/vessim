import argparse
import json
from carbon_aware_control_unit import CarbonAwareControlUnit


def argparser() -> argparse.ArgumentParser:
    # TODO add description=''
    parser = argparse.ArgumentParser()

    parser.add_argument('--server_address',
                        help='address of the API server',
                        default='http://127.0.0.1:8000')

    parser.add_argument('--nodes',
                        metavar='JSON e.g. {"aws": 0, "raspi": 1}',
                        help='names and ids of nodes',
                        required=True)

    parser.add_argument('--until',
                        help='duration of the scenario',
                        default='100')

    return parser


if __name__ == '__main__':

    parser = argparser()
    args = parser.parse_args()
    nodes = json.loads(args.nodes)

    cacu = CarbonAwareControlUnit(args.server_address, nodes)
    cacu.run_scenario(args.until)
