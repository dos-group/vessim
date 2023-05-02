import main

test_args = {
    "START": "2014-01-01 11:00:00",
    "END": 62,  # 30 * 24 * 3600  # 10 days
    "GRID_FILE": "data/custom.json",  # "data/custom.json"  # 'data/demo_lv_grid.json'
    "SOLAR_DATA": "data/pv_10kw.csv",
    "CARBON_DATA": "data/ger_ci_testing.csv",
    "BATTERY_MIN_SOC": 0.6,
    "BATTERY_CAPACITY": 10 * 5 * 3600,  # 10Ah * 5V * 3600 := Ws
    "BATTERY_INITIAL_CHARGE_LEVEL": 0.7,
    "BATTERY_C_RATE": 0.2,
}


def test_solar_and_carbon_data_passing():
    main.main(test_args)
    with open("data.csv") as data_file:
        lines = data_file.readlines()
        assert lines[60] == "0,0.60,126000.00,352.52,0.00,1356.00 "
        assert lines[61] == "1,0.60,126000.00,352.90,0.00,1339.67 "
