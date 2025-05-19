import numpy as np
import time
import sqlite3
import pandas as pd
import requests
import os
from datetime import datetime
from typing import Dict
from pymgrid import Microgrid
from pymgrid.modules import (
    GensetModule,
    BatteryModule,
    LoadModule,
    GridModule,
    RenewableModule,
    NodeModule,
)


def get_column_names(dataframe: pd.DataFrame):
    column_names = dataframe.columns[1:].tolist()

    return column_names


def remove_aggregated_microgrids(gridnames: list[str]):
    country_groups = {}

    # Manually group grid names by their country code
    for name in gridnames:
        country = name[:2]
        if country not in country_groups:
            country_groups[country] = []
        country_groups[country].append(name)

    # Remove 'XX00' only if there are other rows in that group
    result = []
    for country, names in country_groups.items():
        if f"{country}00" in names and len(names) > 1:
            names = [name for name in names if name != f"{country}00"]
        result.extend(names)

    return result


def db_load_retrieve():
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection = sqlite3.connect("database.db")
    cursor = connection.execute(
        "SELECT Node, SUM(CPU) "
        "FROM microgrids "
        "WHERE ? <= Completed_at "
        "GROUP BY Node",
        (current_timestamp,),
    )
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    return rows


def grid_co2_emission(path: str) -> Dict[str, float]:
    """
    Calculates the average hourly carbon intensity (direct) for each Zone ID
    from all CSV files in the given folder path.

    Parameters:
        path (str): The directory containing the CSV files.

    Returns:
        Dict[str, float]: A dictionary mapping each Zone ID to its average
                          carbon intensity in gCO₂eq/kWh.
    """
    zone_carbon_averages = {}

    for filename in os.listdir(path):
        if filename.endswith(".csv"):
            file_path = os.path.join(path, filename)
            df = pd.read_csv(file_path)

            # Ensure the necessary columns are present
            if (
                "Zone id" in df.columns
                and "Carbon intensity gCO₂eq/kWh (direct)" in df.columns
                and not df.empty
            ):
                zone_id = df.iloc[0]["Zone id"]
                avg_carbon = df["Carbon intensity gCO₂eq/kWh (direct)"].mean()

                # Aggregate averages if multiple files per zone
                if zone_id in zone_carbon_averages:
                    zone_carbon_averages[zone_id].append(avg_carbon)
                else:
                    zone_carbon_averages[zone_id] = [avg_carbon]

    # Final average per zone across all files
    return {
        zone: sum(values) / len(values) for zone, values in zone_carbon_averages.items()
    }


def grid_initial_load(c_names: list):
    grid_dict = {}

    for name in c_names:
        for i in range(1, 7):  # 1 through 6
            node_name = f"{name}-{i}"
            grid_dict[node_name] = 120  # Default load value, 120 W.

    return grid_dict


def update_grid_load(grid_dict: dict, rows: list, default_value: float = 120):
    # The corresponding CPU load in watts for each percentage of load
    # Based on the DELL EIPT for a default setting PowerEdge R660 Server with no additional selected processor and 4 x 32 gb RAM.
    cpu_load_watts = {
        "10": 118,
        "20": 180,
        "30": 203,
        "40": 258,
        "50": 281,
        "60": 303,
        "70": 331,
        "80": 349,
        "90": 362,
        "100": 364,
    }
    # Convert rows list to a dictionary for quick lookup
    row_updates = dict(rows)

    for key in grid_dict.keys():
        raw_value = row_updates.get(key, None)

        if raw_value is not None:
            # Round up to nearest 10, cap at 100
            rounded = min(((int(raw_value) + 9) // 10) * 10, 100)
            watt_value = cpu_load_watts.get(str(rounded), default_value)
            grid_dict[key] = watt_value
        else:
            grid_dict[key] = default_value


def generate_grid_modules(c_names: list, co2: dict, final_step: int, electricity_price: dict):
    grid_modules = {}

    for name in c_names:
        co2_value = co2.get(name, 999)  # Use 999 if not found
        electricity_value = electricity_price.get(name, 999)  # Use 999 if not found

        import_price = np.full(final_step, electricity_value)
        export_price = np.full(final_step, electricity_value * 0.9)  # Sell back to the grid for 90% of the import price
        co2_series = np.full(final_step, co2_value)

        time_series = np.array([import_price, export_price, co2_series]).T

        grid = GridModule(max_import=100000, max_export=100000, time_series=time_series)

        grid_modules[name] = grid

    return grid_modules


def generate_battery_modules(c_names: list):
    battery_modules = {}

    for name in c_names:
        battery = BatteryModule(
            min_capacity=0,
            max_capacity=23296.7,  # 101.29 Ahr rougly 23296.7 Wh or 23.3 kWh
            max_charge=2329.67,
            max_discharge=2329.67,
            efficiency=0.9,
            init_soc=0.5,
        )
        battery_modules[name] = battery

    return battery_modules


def generate_node_modules(c_names: list, final_step: int, grid_dict: dict):
    node_modules = {}

    for name in c_names:
        for i in range(1, 7):  # 1 through 6
            node_name = f"{name}-{i}"
            node = NodeModule(
                time_series=60 * np.random.rand(final_step),  # Ignored anyway
                final_step=final_step,
                load=grid_dict[node_name],  # Use the correct full key
                node_name=node_name,
            )
            node_modules[node_name] = node

    return node_modules


def generate_renewable_modules(
    c_names: list, final_step: int, renewable_data: pd.DataFrame
):
    renewable_modules = {}

    for name in c_names:
        renewable = RenewableModule(
            time_series=renewable_data[name],
            final_step=final_step,
        )
        renewable_modules[name] = renewable

    return renewable_modules


def generate_microgrids(
    c_names: list, batteries: dict, nodes: dict, renewables: dict, grids: dict
):
    microgrids = {}

    for name in c_names:
        # Build the list of modules in the correct order
        module_list = [
            batteries[name],
            ("pv_source", renewables[name]),
        ]

        # Add the 6 node modules
        for i in range(1, 7):
            module_list.append(nodes[f"{name}-{i}"])

        # Add the grid module
        module_list.append(grids[name])

        # Create the microgrid
        microgrid = Microgrid(module_list)
        microgrid.grid_name = name
        microgrids[name] = microgrid

    return microgrids


def calculate_final_step(dataframe: pd.DataFrame):
    print("length is ", len(dataframe))

    return len(dataframe) - 1


def export_gridnames_to_csv(gridnames: list[str]):
    filepath = "./data/gridnames.csv"

    # Only write the file if it doesn't already exist
    if not os.path.exists(filepath):
        df = pd.DataFrame(gridnames, columns=["Gridname"])
        df.to_csv(filepath, index=False)

def electricity_price(path: str, gridnames: list[str]):
    """
    Calculates the average electricity price in Euro for each grid name from a CSV file.
    """
    # Load and clean data
    df = pd.read_csv(path, usecols=["geo", "OBS_VALUE"])
    #df = df.dropna(subset=["OBS_VALUE"])

    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE"])

    df["price_per_wh"] = df["OBS_VALUE"] / 1000.0 # Convert from kWh to Wh 

    country_avg = df.groupby("geo")["price_per_wh"].mean()

    overall_avg = df["price_per_wh"].mean()

    result = {code: country_avg.get(code, overall_avg) for code in gridnames}

    return result

def main():
    # Load the solar data and setup variables for microgrid setup
    df_solar = pd.read_csv("data/solarPV.csv")
    column_names_aggregated = get_column_names(df_solar)
    column_names = remove_aggregated_microgrids(column_names_aggregated)
    # print(column_names)
    export_gridnames_to_csv(column_names)
    final_step = calculate_final_step(df_solar)

    # Create the initial grid load dictionary, with everything set to 0.0
    grid_dict = grid_initial_load(column_names)
    # print(grid_dict)

    # Test Co2 emission data
    average_co2 = grid_co2_emission("data/emissions")
    # print("length is: ", len(average_co2))
    # print(average_co2)

    # Create dict for electricity price
    electricity_price_dict = electricity_price("data/estat_nrg_pc_204.csv", column_names)
    #print(electricity_price_dict)

    # Generate the battery, node, renewable and microgrid modules
    batteries = generate_battery_modules(column_names)
    nodes = generate_node_modules(column_names, final_step, grid_dict)
    # print("amount of nodes is: ", len(nodes))
    renewables = generate_renewable_modules(column_names, final_step, df_solar)
    grids = generate_grid_modules(column_names, average_co2, final_step, electricity_price_dict)
    microgrids = generate_microgrids(column_names, batteries, nodes, renewables, grids)
    print("amount of microgrids is: ", len(microgrids))

    # Create the empty action, which will be updated with the load values
    custom_action = microgrids["ES10"].get_empty_action(sample_flex_modules=False)
    print(custom_action)

    #
    # The actual simulation with updating loads, actions and logging
    #

    # update_grid_load(grid_dict=grid_dict, rows=rows)
    # print(grid_dict["ES10"], grid_dict["PT02"], grid_dict["ES12"])

    # microgrid.reset()

    wait_time = (
        120  # 120 seconds to make the simulation 30x times faster than real time.
    )
    starttime = time.monotonic()

    state_of_charge = []

    total_capacity_of_installations = (
        1800.0  # W, such that it cannot fully cover the load of nodes at full capacity
    )

    while True:
        # for j in range(24):
        # time.sleep(wait_time - ((time.monotonic() - starttime) % wait_time))
        state_of_charge.clear()
        rows = db_load_retrieve()
        print("Selected rows ", rows)
        print("Grid dict before update ", grid_dict)
        update_grid_load(grid_dict=grid_dict, rows=rows)

        for microgrid in microgrids.values():
            print("Microgrid Name: ", microgrid.grid_name)

            load = 0.0
            net_load = 0.0

            for i in range(0, 6):
                # print(microgrid.modules.node[i].node_name)
                microgrid.modules.node[i].update_current_load(
                    grid_dict[microgrid.modules.node[i].node_name]
                )

                load += -1.0 * microgrid.modules.node[i].current_load

            pv = (
                microgrid.modules.pv_source[0].current_renewable
                * total_capacity_of_installations
            )

            net_load = load + pv
            # if net_load > 0:
            #     net_load = 0.0

            battery_discharge = min(
                -1 * net_load, microgrid.modules.battery[0].max_production
            )
            # print("Battery discharge ", battery_discharge)
            net_load += battery_discharge

            grid_import = min(
                -1 * net_load, microgrid.modules.grid.item().max_production
            )
            # print("Grid import ", grid_import)

            # Total load of all nodes in the microgrid
            total_load = (
                microgrid.modules.node[0].current_load
                + microgrid.modules.node[1].current_load
                + microgrid.modules.node[2].current_load
                + microgrid.modules.node[3].current_load
                + microgrid.modules.node[4].current_load
                + microgrid.modules.node[5].current_load
            )

            total_grid_dict_load = (
                grid_dict[microgrid.modules.node[0].node_name]
                + grid_dict[microgrid.modules.node[1].node_name]
                + grid_dict[microgrid.modules.node[2].node_name]
                + grid_dict[microgrid.modules.node[3].node_name]
                + grid_dict[microgrid.modules.node[4].node_name]
                + grid_dict[microgrid.modules.node[5].node_name]
            )

            print("Load ", total_load)
            print("Grid dict load ", total_grid_dict_load)
            print(
                "Renewable ",
                microgrid.modules.pv_source[0].current_renewable
                * total_capacity_of_installations,
            )
            print("Battery SOC ", microgrid.modules.battery[0].soc)
            print(
                "Battery level of charge ", microgrid.modules.battery[0].current_charge
            )

            # custom_action.update(
            #     {
            #         "battery": [
            #             microgrid.modules.node[0].current_load
            #             - (microgrid.modules.pv_source[0].current_renewable * total_capacity_of_installations) # The current_renewable is a PECD value, so we need to multiply it with the total capacity of the installations to find out the kW value of the step.
            #         ],
            #         "grid": [microgrid.modules.grid[0].grid_status[0]]
            #     }
            # )
            custom_action.update(
                {
                    "battery": [battery_discharge],
                    "grid": [grid_import],
                }
            )
            print("Custom action ", custom_action)

            microgrid.step(custom_action, normalized=False)

            log = microgrid.get_log()
            filename = f"logs/{microgrid.grid_name}.csv"
            os.makedirs("logs", exist_ok=True)
            file_exists = os.path.isfile(filename)
            log.to_csv(filename, mode="a", header=not file_exists, index=False)

            state_of_charge.append(
                {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOC": microgrid.modules.battery[0].soc,
                    "Current_renewable": microgrid.modules.pv_source[
                        0
                    ].current_renewable
                    * total_capacity_of_installations,
                    "Current_load": total_load,
                    "Gridname": microgrid.grid_name,
                }
            )
            # print(shared_state.state_of_charge)

        # API STUFF
        url = "http://127.0.0.1:5000/insert"
        data = {"data": state_of_charge}
        response = requests.post(url, json=data)
        print(response.status_code, response.json())
        time.sleep(wait_time)

    # Logging and visualization of the data

    # df = microgrid.get_log()
    # compute_net_load

    # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # filename = f"logs/log-{timestamp}.csv"
    # df.to_csv(filename, index=False)


if __name__ == "__main__":
    main()
