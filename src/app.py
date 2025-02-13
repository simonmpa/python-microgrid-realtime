import numpy as np
import time
from datetime import datetime
from pymgrid import Microgrid
from pymgrid.modules import GensetModule, BatteryModule, LoadModule, RenewableModule, NodeModule


genset = GensetModule(running_min_production=10,
                      running_max_production=50,
                      genset_cost=0.5)

battery = BatteryModule(min_capacity=0,
                        max_capacity=100,
                        max_charge=50,
                        max_discharge=50,
                        efficiency=1.0,
                        init_soc=0.5)

# Using random data
renewable = RenewableModule(time_series=50*np.random.rand(100))

load = LoadModule(time_series=60*np.random.rand(100))

node = NodeModule(time_series=60*np.random.rand(100))

microgrid = Microgrid([genset, battery, ("pv", renewable), load, node])



wait_time = 15.0
starttime = time.monotonic()

# while True:
#     microgrid.step(microgrid.sample_action())
#     print(microgrid.get_log())
#     time.sleep(wait_time - ((time.monotonic() - starttime) % wait_time))

for j in range(10):
    microgrid.step(microgrid.sample_action())

df = microgrid.get_log()
df.to_csv('logs/log.csv' + datetime.now(), index=False)