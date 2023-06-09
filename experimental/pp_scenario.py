import pandapower as pp

# create empty net
import pandas as pd

net = pp.create_empty_network(f_hz=50.0)

# create buses
b1 = pp.create_bus(net, vn_kv=0.4, name="bus1")
b2 = pp.create_bus(net, vn_kv=0.4, name="bus2")
b3 = pp.create_bus(net, vn_kv=0.4, name="bus3")

# create bus elements
pp.create_ext_grid(
    net, bus=b1, vm_pu=1.02, name="grid connection"
)  # TODO Why voltage 1.02 pu https://github.com/e2nIEE/pandapower/blob/develop/tutorials/minimal_example.ipynb
pp.create_load(net, bus=b3, p_mw=0.1, q_mvar=0.05, name="load")

# create branch elements
pp.create_line(
    net,
    from_bus=b1,
    to_bus=b2,
    length_km=0.1,
    name="line1",
    std_type="NAYY 4x50 SE",
)
pp.create_line(
    net,
    from_bus=b2,
    to_bus=b3,
    length_km=0.1,
    name="line2",
    std_type="NAYY 4x50 SE",
)

with pd.option_context("display.expand_frame_repr", False):
    print("\nBus")
    print(net.bus)
    print("\nLine")
    print(net.line)
    print("\nLoad")
    print(net.load)

print("\n---------------\nSOLVE\n---------------")
pp.runpp(net)

with pd.option_context("display.expand_frame_repr", False):
    print("\nResult: Ext Grid")
    print(net.res_ext_grid)
    print("\nResult: Bus")
    print(net.res_bus)
    print("\nResult: Line")
    print(net.res_line)
    print("\nResult: Load")
    print(net.res_load)

pp.to_json(net, filename="data/custom.json")
