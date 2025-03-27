import numpy as np
import time
import sqlite3
from datetime import datetime
import pandas as pd
from pymgrid import Microgrid
from pymgrid.modules import (
    GensetModule,
    BatteryModule,
    LoadModule,
    RenewableModule,
    NodeModule,
)


def get_column_names(dataframe: pd.DataFrame):
    column_string_lists = []

    for column in dataframe.columns[1:]:
        string_list = [str(value) for value in dataframe[column].values]
        column_string_lists.append(string_list)

    return column_string_lists


def db_load_retrieve(last_timestamp: str):
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection = sqlite3.connect("database.db")
    cursor = connection.execute(
        "SELECT Gridname, SUM(Load) "
        "FROM microgrids "
        "WHERE Timestamp BETWEEN ? AND ? "
        "GROUP BY Gridname",
        (last_timestamp, current_timestamp),
    )
    rows = cursor.fetchall()
    cursor.close()
    connection.close()

    return rows


def grid_load(dataframe: pd.DataFrame):
    grid_dict = {}

    for column in dataframe.columns[1:]:
        grid_dict[column] = 0.0

    return grid_dict


def update_grid_load(grid_dict: dict, rows: list):
    for grid_name, load_value in rows:
        if grid_name in grid_dict:
            grid_dict[grid_name] = load_value


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
            time_series=60 * np.random.rand(final_step),
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
            [batteries[name], ("pv_" + name, renewables[name]), nodes[name]]
        )
        microgrids[name] = microgrid

    return microgrids


def calculate_final_step(dataframe: pd.DataFrame):
    print("length is ", len(dataframe))
    return len(dataframe - 1)


def main():
    df_solar = pd.read_csv("data/solarPV.csv")
    column_names = get_column_names(df_solar)
    final_step = calculate_final_step(df_solar)

    batteries = generate_battery_modules(column_names)
    nodes = generate_node_modules(column_names, final_step, grid_dict)
    renewables = generate_renewable_modules(column_names, final_step, df_solar)
    microgrids = generate_microgrids(column_names, batteries, nodes, renewables)

    custom_action = microgrids["ES10"].get_empty_action()

    grid_dict = grid_load(df_solar)
    print(grid_dict["ES10"], grid_dict["PT02"], grid_dict["ES12"])

    rows = db_load_retrieve("2025-03-25 13:00:19")

    # print(rows)

    update_grid_load(grid_dict=grid_dict, rows=rows)
    print(grid_dict["ES10"], grid_dict["PT02"], grid_dict["ES12"])

    # spain = df_solar["ES10"]
    # print(spain.head(24))

    # Determine the final step based on your data length
    # final_step = len(spain)

    # battery = BatteryModule(
    #     min_capacity=0,
    #     max_capacity=100,
    #     max_charge=50,
    #     max_discharge=50,
    #     efficiency=1.0,
    #     init_soc=0.5,
    # )

    # renewable_solar = RenewableModule(time_series=spain, final_step=final_step)

    # node = NodeModule(
    #     time_series=60 * np.random.rand(final_step),
    #     final_step=final_step,
    #     load=grid_dict["ES10"],
    # )

    # microgrid = Microgrid([battery, ("pv_spain", renewable_solar), node])

    wait_time = 15.0
    starttime = time.monotonic()

    # while True:
    #     microgrid.step(microgrid.sample_action())
    #     print(microgrid.get_log())
    #     time.sleep(wait_time - ((time.monotonic() - starttime) % wait_time))

    # microgrid.reset()

    # custom_action = microgrid.get_empty_action()

    print(custom_action)

    for j in range(24):
        # custom_action = microgrid.get_empty_action()
        # print(microgrid.modules.pv_spain[0].current_renewable)

        custom_action.update(
            {
                "battery": [
                    microgrid.modules.node[0].current_load
                    - (microgrid.modules.pv_spain[0].current_renewable * 10)
                ]
            }
        )

        # print(custom_action)
        microgrid.step(custom_action)

    df = microgrid.get_log()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"logs/log-{timestamp}.csv"
    df.to_csv(filename, index=False)


if __name__ == "__main__":
    main()
