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
    """
    Gets the column names from the dataframe, which is the grid names.
    """
    column_names = dataframe.columns[1:].tolist()

    return column_names


def remove_aggregated_microgrids(gridnames: list[str]):
    """
    Remove the 'XX00' grid names from the list if there are other grid names in the same country.
    """
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
    """
    Retrieve the CPU load from the database for each node in the microgrid.
    Only retrieves CPU loads that are not completed yet.
    """
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
    Returns values in gCO₂ per Wh.
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
                avg_carbon_kwh = df["Carbon intensity gCO₂eq/kWh (direct)"].mean()
                avg_carbon_wh = avg_carbon_kwh / 1000  # From kWh to Wh

                # Aggregate averages if multiple files per zone
                if zone_id in zone_carbon_averages:
                    zone_carbon_averages[zone_id].append(avg_carbon_wh)
                else:
                    zone_carbon_averages[zone_id] = [avg_carbon_wh]

    # Final average per zone across all files
    return {
        zone: sum(values) / len(values) for zone, values in zone_carbon_averages.items()
    }


def grid_initial_load(c_names: list):
    """
    Create a dictionary with the initial load for each node in the grid.
    The default load value is set to 120 W based on the Dell EIPT.
    """
    grid_dict = {}

    for name in c_names:
        for i in range(1, 7):  # 1 through 6
            node_name = f"{name}-{i}"
            grid_dict[node_name] = 120  # Default load value, 120 W.

    return grid_dict


def update_grid_load(grid_dict: dict, rows: list, default_value: float = 120):
    """ 
    The corresponding CPU load in watts for each percentage of load.
    Based on the DELL EIPT for a default setting PowerEdge R660 Server with no additional selected processor and 4 x 32 gb RAM.
    """
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

    row_updates = dict(rows)

    for key in grid_dict.keys():
        raw_value = row_updates.get(key, None)

        if raw_value is not None:
            # Round to nearest 10, cap at 100
            rounded = min(round(float(raw_value) / 10) * 10, 100) # If the CPU load is closer to 0%, set to default_value and if it is closer to 10% set to 10%.
            watt_value = cpu_load_watts.get(str(rounded), default_value)
            grid_dict[key] = watt_value
        else:
            grid_dict[key] = default_value


def generate_grid_modules(c_names: list, co2: dict, final_step: int, electricity_price: dict):
    grid_modules = {}

    for name in c_names:
        country_code = name[:2]
        co2_value = co2.get(country_code, 999)  # Default to 999 given not found
        print(co2_value)
        electricity_value = electricity_price.get(country_code, 888)  # Default to 888 given not found

        import_price = np.full(final_step, electricity_value)
        export_price = np.full(final_step, electricity_value * 0.9)  # 90% of import price
        co2_series = np.full(final_step, co2_value)

        time_series = np.array([import_price, export_price, co2_series]).T

        grid = GridModule(max_import=100000, max_export=100000, time_series=time_series)

        grid_modules[name] = grid

    return grid_modules


def generate_battery_modules(c_names: list):
    """
    Generate the battery modules for each grid name in the c_names list.
    """
    battery_modules = {}

    for name in c_names:
        battery = BatteryModule(
            min_capacity=0,
            max_capacity=23296.7,  # 101.29 Ahr rougly 23296.7 Wh or 23.3 kWh
            max_charge=2329.67, # can maximum charge 10% of the battery capacity in 1 step
            max_discharge=2329.67, # can maximum discharge 10% of the battery capacity in 1 step
            efficiency=0.9,
            init_soc=0.5,
        )
        battery_modules[name] = battery

    return battery_modules


def generate_node_modules(c_names: list, final_step: int, grid_dict: dict):
    """
    Generate the node modules for each grid name in the c_names list.
    The load is set to the value in the grid_dict for each node.
    """
    node_modules = {}

    for name in c_names:
        for i in range(1, 7):  # 1 through 6
        #for i in range (1, 3):
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
    """
    Generate the renewable modules for each grid name in the c_names list.
    The renewable data is a dataframe with the renewable data for each grid name, which is a utilization value between 0-100%.
    """
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
        #for i in range(1, 3):
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
    """
    Export the grid names to a CSV file.
    """
    filepath = "./data/gridnames.csv"

    if not os.path.exists(filepath):
        df = pd.DataFrame(gridnames, columns=["Gridname"])
        df.to_csv(filepath, index=False)

def electricity_price(path: str, gridnames: list[str]):
    """
    Calculates the average electricity price in Euro for each grid name from a CSV file.
    """
    df = pd.read_csv(path, usecols=["geo", "OBS_VALUE"])

    df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
    df = df.dropna(subset=["OBS_VALUE"])

    df["price_per_wh"] = df["OBS_VALUE"] / 1000.0 # Convert from kWh to Wh

    country_avg = df.groupby("geo")["price_per_wh"].mean()

    overall_avg = df["price_per_wh"].mean()

    result = {code: country_avg.get(code, overall_avg) for code in gridnames}

    return result

def prune_and_forward_fill_solar_data(dataframe: pd.DataFrame):
    # Load the CSV file with datetime parsing
    df = dataframe

    # Set 'Time' as index
    df.set_index("Time", inplace=True)
    df.sort_index(inplace=True)  # Make sure the index is sorted for slicing

    # Slice only the 2016–2019 range
    df_pruned = df.loc["2016-01-01":"2019-12-31"]

    # Create new 10-minute interval index
    new_index = pd.date_range(start="2016-01-01", end="2019-12-31 23:50:00", freq="10T")

    # Reindex and forward-fill
    df_10min = df_pruned.reindex(new_index)
    df_10min.ffill(inplace=True)

    # Reset index to make 'Time' a column again
    df_10min.reset_index(inplace=True)
    df_10min.rename(columns={"index": "Time"}, inplace=True)

    # Format 'Time' column back to 'dd-MMM-yyyy HH:MM:SS' format (e.g., 31-Dec-2019 23:50:00)
    df_10min["Time"] = df_10min["Time"].dt.strftime("%d-%b-%Y %H:%M:%S")

    # Save to a new CSV file
    df_10min.to_csv("data/solarPV_10min.csv", index=False)

    return df_10min

def main():
    # Load the solar data and setup variables for microgrid setup
    df = pd.read_csv("data/solarPV.csv", dayfirst=True, parse_dates=["Time"])
    df_solar = prune_and_forward_fill_solar_data(df)
    #df_solar = pd.read_csv("data/solarPV.csv")
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
        #1800.0  # W, such that it cannot fully cover the load of nodes at full capacity
        3600.0 # W, such that it cannot fully cover the load of nodes at full capacity
    )

    while True:
        # for j in range(24):
        # time.sleep(wait_time - ((time.monotonic() - starttime) % wait_time))
        state_of_charge.clear()
        rows = db_load_retrieve()
        print("Selected rows ", rows)
        #print("Grid dict before update ", grid_dict)
        update_grid_load(grid_dict=grid_dict, rows=rows)
        # print("------------------------------------------------------------")
        # print("Grid dict after update ", grid_dict)

        for microgrid in microgrids.values():
            print("Microgrid Name: ", microgrid.grid_name) # Add this back if it's part of your logging sequence here

            load = 0.0
            net_load = 0.0

            for i in range(0, 6):
            #for i in range(0, 2):
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

            battery_command = 0.0
            grid_command = 0.0
            
            current_soc = microgrid.modules.battery[0].soc

            battery_max_charge_power = microgrid.modules.battery[0].max_consumption
            battery_max_discharge_power = microgrid.modules.battery[0].max_production
            grid_max_export_power = microgrid.modules.grid.item().max_consumption
            grid_max_import_power = microgrid.modules.grid.item().max_production

            if net_load > 0:
                surplus_power = net_load
                if current_soc < 0.999: 
                    charge_to_battery = min(surplus_power, battery_max_charge_power)
                    battery_command = -charge_to_battery
                    
                    remaining_surplus = surplus_power - charge_to_battery
                    if remaining_surplus > 0:
                        export_to_grid = min(remaining_surplus, grid_max_export_power)
                        grid_command = -export_to_grid
                else: 
                    battery_command = 0.0 
                    export_to_grid = min(surplus_power, grid_max_export_power)
                    grid_command = -export_to_grid

            elif net_load < 0:
                deficit_power = -net_load 
                discharge_from_battery = min(deficit_power, battery_max_discharge_power)
                battery_command = discharge_from_battery
                
                remaining_deficit = deficit_power - discharge_from_battery
                if remaining_deficit > 0:
                    import_from_grid = min(remaining_deficit, grid_max_import_power)
                    grid_command = import_from_grid

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
            print("Battery SOC ", microgrid.modules.battery[0].soc) # This is current_soc before action
            print(
                "Battery level of charge ", microgrid.modules.battery[0].current_charge # Before action
            )

            custom_action.update(
                {
                    "battery": [battery_command],
                    "grid": [grid_command],
                }
            )
            print("Custom action ", custom_action)

            microgrid.step(custom_action, normalized=False)

            log = microgrid.get_log(as_frame=True, drop_forecasts=True)
            filename = f"logs/{microgrid.grid_name}.csv"
            os.makedirs("logs", exist_ok=True)
            log.to_csv(filename, mode="w", header=True, index=False)

            state_of_charge.append(
                {
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "SOC": microgrid.modules.battery[0].soc * 100,
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
