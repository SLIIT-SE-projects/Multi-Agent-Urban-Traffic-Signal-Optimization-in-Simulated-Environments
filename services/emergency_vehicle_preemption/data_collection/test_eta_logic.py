import pandas as pd
import numpy as np

df = pd.read_csv("D:/Thilan/UNI/Research/implementations/repo 9 clean/multi-agent-urban-traffic-signal-optimization-in-simulated-environments/services/emergency_vehicle_preemption/data/raw/massive_eta_data.csv")
print(df.head())

# Filter one EV
sample_ev = df['ev_id'].unique()[0]
ev_data = df[df['ev_id'] == sample_ev].sort_values('step')

print(f"Total steps for {sample_ev}: {len(ev_data)}")
# Calculate drops/increases in distance
diffs = ev_data['distance_to_signal'].diff()

print("Distance diffs where it increased (crossed intersection):")
print(ev_data[diffs > 10][['step', 'distance_to_signal']])
