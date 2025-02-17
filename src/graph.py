import pandas as pd
import matplotlib.pyplot as plt

# Load the CSV file into a pandas DataFrame
df = pd.read_csv('logs/log-2025-02-17_13-01-25.csv')

# 1. Battery State of Charge (SOC) over Time
plt.figure(figsize=(10, 6))  # Adjust figure size for better readability
plt.plot(df.index, df['charge_amount', 'current_charge', 'discharge_amount', 'reward', 'soc'], label='Battery SOC')
plt.xlabel('Time')
plt.ylabel('State of Charge (SOC)')
plt.title('Battery SOC over Time')
plt.legend()
plt.grid(True)  # Add a grid for better readability
plt.show()
