import numpy as np
import time
from datetime import datetime
import pandas as pd
from pymgrid import Microgrid
from pymgrid.modules import GensetModule, BatteryModule, LoadModule, RenewableModule, NodeModule

df_solar = pd.read_csv('data/solarPV.csv')



spain = df_solar["ES10"]
print(spain.head(24))

# Determine the final step based on your data length
final_step = len(spain)  # Or however you determine the end of your simulation

#np.random.seed(0)

genset = GensetModule(running_min_production=10,
                      running_max_production=50,
                      genset_cost=0.5)

battery = BatteryModule(min_capacity=0,
                        max_capacity=100,
                        max_charge=50,
                        max_discharge=50,
                        efficiency=1.0,
                        init_soc=0.5)

renewable_solar = RenewableModule(time_series=spain, final_step=final_step)

load = LoadModule(time_series=60*np.random.rand(final_step), final_step=final_step)

node = NodeModule(time_series=60*np.random.rand(final_step), final_step=final_step)

# microgrid = Microgrid([genset, battery, ("pv", renewable), ("pv_spain", renewable_solar),load, node])
microgrid = Microgrid([battery, ("pv_spain", renewable_solar), load, node])

print(microgrid.get_empty_action())


wait_time = 15.0
starttime = time.monotonic()

# while True:
#     microgrid.step(microgrid.sample_action())
#     print(microgrid.get_log())
#     time.sleep(wait_time - ((time.monotonic() - starttime) % wait_time))

microgrid.reset()

for j in range(24):
    empty_action = microgrid.get_empty_action()
    #print((renewable_solar.current_renewable * 10))

    #print(microgrid.modules.load.item().current_load)
    #print(microgrid.modules.battery[0].current_charge)
    print(microgrid.modules.pv_spain[0].current_renewable)

    #load = -1.0 * microgrid.modules

    empty_action.update({'battery': [node.current_load - ((renewable_solar.current_renewable) * 10)]})

    action = microgrid.sample_action(strict_bound=True)

    print(action)
    microgrid.step(action)

df = microgrid.get_log()

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
filename = f"logs/log-{timestamp}.csv"
df.to_csv(filename, index=False)