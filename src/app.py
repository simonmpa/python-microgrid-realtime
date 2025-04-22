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


def db_load_retrieve():
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection = sqlite3.connect("database.db")
    cursor = connection.execute(
        "SELECT Gridname, SUM(Load) "
        "FROM microgrids "
        "WHERE ? <= Completed_at "
        "GROUP BY Gridname",
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
        if filename.endswith('.csv'):
            file_path = os.path.join(path, filename)
            df = pd.read_csv(file_path)

            # Ensure the necessary columns are present
            if 'Zone id' in df.columns and 'Carbon intensity gCO₂eq/kWh (direct)' in df.columns and not df.empty:
                zone_id = df.iloc[0]['Zone id']
                avg_carbon = df['Carbon intensity gCO₂eq/kWh (direct)'].mean()

                # Aggregate averages if multiple files per zone
                if zone_id in zone_carbon_averages:
                    zone_carbon_averages[zone_id].append(avg_carbon)
                else:
                    zone_carbon_averages[zone_id] = [avg_carbon]

    # Final average per zone across all files
    return {
        zone: sum(values) / len(values)
        for zone, values in zone_carbon_averages.items()
    }


def grid_initial_load(c_names: list):
    grid_dict = {name: 0.0 for name in c_names}

    return grid_dict


def update_grid_load(grid_dict: dict, rows: list, default_value: float = 0.0):
    # for grid_name, load_value in rows:
    #     if grid_name in grid_dict:
    #         grid_dict[grid_name] = load_value

    # Convert rows list to a dictionary for quick lookup
    row_updates = dict(rows)

    # Update grid_dict in a single loop
    for key in grid_dict.keys():
        grid_dict[key] = row_updates.get(key, default_value)


def generate_grid_modules(c_names: list, co2: dict, final_step: int):
    grid_modules = {}

    for name in c_names:
        co2_value = co2.get(name, 999)  # Use 999 if not found

        import_price = np.ones(final_step)
        export_price = np.ones(final_step)
        co2_series = np.full(final_step, co2_value)

        time_series = np.array([
            import_price,
            export_price,
            co2_series
        ]).T

        grid = GridModule(
            max_import=1000,
            max_export=100,
            time_series=time_series
        )

        grid_modules[name] = grid

    return grid_modules

def generate_battery_modules(c_names: list):
    battery_modules = {}

    for name in c_names:
        battery = BatteryModule(
            min_capacity=0,
            max_capacity=100,
            max_charge=50,
            max_discharge=50,
            efficiency=1.0,
            init_soc=0.5,
        )
        battery_modules[name] = battery

    return battery_modules


def generate_node_modules(c_names: list, final_step: int, grid_dict: dict):
    node_modules = {}

    for name in c_names:
        node = NodeModule(
            time_series=60
            * np.random.rand(
                final_step
            ),  # Denne parameter bliver overridet på klassen af vores load, så den er ligegyldig (orker ikke at rode med at fjerne den fra klassen)
            final_step=final_step,
            load=grid_dict[name],
        )
        node_modules[name] = node

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


def generate_microgrids(c_names: list, batteries: dict, nodes: dict, renewables: dict, grids: dict):
    microgrids = {}

    for name in c_names:
        microgrid = Microgrid(
            [batteries[name], ("pv_source", renewables[name]), nodes[name], grids[name]]
        )
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

def main():
    # Load the solar data and setup variables for microgrid setup
    df_solar = pd.read_csv("data/solarPV.csv")
    column_names = get_column_names(df_solar)
    export_gridnames_to_csv(column_names)
    print(column_names)
    final_step = calculate_final_step(df_solar)

    # Create the initial grid load dictionary, with everything set to 0.0
    grid_dict = grid_initial_load(column_names)
    print(grid_dict)

    # Test Co2 emission data
    average_co2 = grid_co2_emission("data/emissions")
    print("length is: ", len(average_co2))
    print(average_co2)

    # Generate the battery, node, renewable and microgrid modules
    batteries = generate_battery_modules(column_names)
    nodes = generate_node_modules(column_names, final_step, grid_dict)
    renewables = generate_renewable_modules(column_names, final_step, df_solar)
    grids = generate_grid_modules(column_names, average_co2, final_step)
    microgrids = generate_microgrids(column_names, batteries, nodes, renewables, grids)

    # Create the empty action, which will be updated with the load values
    custom_action = microgrids["ES10"].get_empty_action()
    print(custom_action)

    #
    # The actual simulation with updating loads, actions and logging
    #

    # update_grid_load(grid_dict=grid_dict, rows=rows)
    # print(grid_dict["ES10"], grid_dict["PT02"], grid_dict["ES12"])

    # microgrid.reset()

    wait_time = 5.0
    starttime = time.monotonic()

    state_of_charge = []

    total_capacity_of_installations = 25.0 # kW

    while True:
        # for j in range(24):
        # time.sleep(wait_time - ((time.monotonic() - starttime) % wait_time))
        time.sleep(wait_time)

        state_of_charge.clear()
        rows = db_load_retrieve()
        print("Selected rows ", rows)
        update_grid_load(grid_dict=grid_dict, rows=rows)

        for microgrid in microgrids.values():
            print(microgrid.grid_name)

            microgrid.modules.node[0].update_current_load(
                grid_dict[microgrid.grid_name]
            )

            load = -1.0 * microgrid.modules.node[0].current_load
            pv = microgrid.modules.pv_source[0].current_renewable * total_capacity_of_installations

            net_load = load + pv
            if net_load > 0:
                net_load = 0.0

            battery_discharge = min(-1 * net_load, microgrid.modules.battery[0].max_production)
            net_load += battery_discharge

            grid_import = min(-1*net_load, microgrid.modules.grid.item().max_production)

            print("Load ", microgrid.modules.node[0].current_load)
            print("Grid dict load ", grid_dict[microgrid.grid_name])
            print("Renewable ", microgrid.modules.pv_source[0].current_renewable)
            print("Grid import ", microgrid.modules.grid[0].grid_status[0])

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

            microgrid.step(custom_action)

            state_of_charge.append(
                {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOC": microgrid.modules.battery[0].soc,
                    "Current_renewable": microgrid.modules.pv_source[
                        0
                    ].current_renewable,
                    "Current_load": microgrid.compute_net_load(),
                    "Gridname": microgrid.grid_name,
                }
            )
            # print(shared_state.state_of_charge)

        # API STUFF
        url = "http://127.0.0.1:5000/insert"
        data = {"data": state_of_charge}
        response = requests.post(url, json=data)
        print(response.status_code, response.json())

    # Logging and visualization of the data

    # df = microgrid.get_log()
    # compute_net_load

    # timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # filename = f"logs/log-{timestamp}.csv"
    # df.to_csv(filename, index=False)


if __name__ == "__main__":
    main()
