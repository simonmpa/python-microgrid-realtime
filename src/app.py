import numpy as np
import time
import sqlite3
import pandas as pd
import requests
import os
from datetime import datetime
from pymgrid import Microgrid
from pymgrid.modules import (
    GensetModule,
    BatteryModule,
    LoadModule,
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


def generate_microgrids(c_names: list, batteries: dict, nodes: dict, renewables: dict):
    microgrids = {}

    for name in c_names:
        microgrid = Microgrid(
            [batteries[name], ("pv_source", renewables[name]), nodes[name]]
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

    # Generate the battery, node, renewable and microgrid modules
    batteries = generate_battery_modules(column_names)
    nodes = generate_node_modules(column_names, final_step, grid_dict)
    renewables = generate_renewable_modules(column_names, final_step, df_solar)
    microgrids = generate_microgrids(column_names, batteries, nodes, renewables)

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

            print("Load ", microgrid.modules.node[0].current_load)
            print("Grid dict load ", grid_dict[microgrid.grid_name])
            print("Renewable ", microgrid.modules.pv_source[0].current_renewable)

            custom_action.update(
                {
                    "battery": [
                        microgrid.modules.node[0].current_load
                        - (microgrid.modules.pv_source[0].current_renewable * 10)
                    ]
                }
            )

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
