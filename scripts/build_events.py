"""Build the constructed IIoT events dataset from the original AI4I 2020 records.

Input : data/raw/ai4i2020.csv  (Matzka 2020, UCI ML Repository, DOI 10.24432/C5HS5C, CC BY 4.0)
Output: data/constructed/events.csv, machines.csv, rejected_records.csv
All constructed values are deterministic (no random numbers) so the graph can be rebuilt exactly.
"""
import pandas as pd, numpy as np, math, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
raw = pd.read_csv(ROOT/'data/raw/ai4i2020.csv', encoding='utf-8-sig')
raw.columns = ['udi','product_id','product_type','air_temp_k','process_temp_k','rpm','torque_nm',
               'tool_wear_min','machine_failure','TWF','HDF','PWF','OSF','RNF']

# --- constructed scenario parameters (thesis simulation, documented assumptions) ---
BLOCK = 2500                                   # consecutive UDI blocks -> one machine each
MACHINES = {1:('CNC-01','LINE-A'),2:('CNC-02','LINE-A'),3:('CNC-03','LINE-B'),4:('CNC-04','LINE-B')}
START = pd.Timestamp('2026-10-01 06:00:00')    # replay start of the IIoT stream
CYCLE_MIN = 5                                  # one AI4I record = one 5-minute production cycle
DOWNTIME = {'TWF':25,'HDF':45,'PWF':60,'OSF':35,'RNF':15,'UNSPECIFIED':15}   # minutes, unplanned
TOOL_CHANGE_MIN = 10                           # planned
MODES = ['TWF','HDF','PWF','OSF','RNF']

raw['machine_no'] = (raw.udi-1)//BLOCK + 1
raw['machine_id'] = raw.machine_no.map(lambda k: MACHINES[k][0])
raw['line_id']    = raw.machine_no.map(lambda k: MACHINES[k][1])
raw['cycle_no']   = (raw.udi-1) % BLOCK
raw['timestamp']  = START + pd.to_timedelta(raw.cycle_no*CYCLE_MIN, unit='min')
raw['power_w']    = (raw.torque_nm * raw.rpm * 2*math.pi/60).round(0).astype(int)
raw['temp_delta_k'] = (raw.process_temp_k - raw.air_temp_k).round(1)

events, rejected = [], []
prev_wear = {}
for r in raw.itertuples(index=False):
    flags = [m for m in MODES if getattr(r, m) == 1]
    # planned tool change: tool wear counter resets inside the same machine block
    pw = prev_wear.get(r.machine_id)
    if pw is not None and r.tool_wear_min < pw:
        events.append(dict(event_id=f'TC-{r.udi:05d}', event_type='TOOL_CHANGE', planned=True,
            failure_modes='', downtime_min=TOOL_CHANGE_MIN, kpi_affected='Availability',
            scrap_parts=0))
        events[-1].update(source_udi=r.udi)
    prev_wear[r.machine_id] = r.tool_wear_min
    if r.machine_failure == 1:
        modes = flags or ['UNSPECIFIED']
        events.append(dict(event_id=f'EVT-{r.udi:05d}', event_type='FAILURE', planned=False,
            failure_modes='|'.join(modes), downtime_min=max(DOWNTIME[m] for m in modes),
            kpi_affected='Availability|Quality', scrap_parts=1, source_udi=r.udi))
    elif flags:   # failure-mode flag set but machine_failure = 0 -> does not fit schema
        rejected.append(dict(source_udi=r.udi, reason='mode flag without machine_failure', flags='|'.join(flags)))

ev = pd.DataFrame(events)
cols_orig = ['udi','product_id','product_type','air_temp_k','process_temp_k','rpm','torque_nm','tool_wear_min']
ev = ev.merge(raw[cols_orig+['machine_id','line_id','timestamp','power_w','temp_delta_k']],
              left_on='source_udi', right_on='udi').drop(columns='udi')
order = ['event_id','source_udi','machine_id','line_id','timestamp','event_type','planned','failure_modes',
         'downtime_min','kpi_affected','scrap_parts','product_id','product_type','air_temp_k','process_temp_k',
         'temp_delta_k','rpm','torque_nm','power_w','tool_wear_min']
ev = ev[order].sort_values(['timestamp','machine_id']).reset_index(drop=True)
out = ROOT/'data/constructed'; out.mkdir(parents=True, exist_ok=True)
ev.to_csv(out/'events.csv', index=False)
pd.DataFrame(rejected).to_csv(out/'rejected_records.csv', index=False)
m = raw.groupby(['machine_id','line_id']).agg(udi_from=('udi','min'), udi_to=('udi','max'), cycles=('udi','size')).reset_index()
m['machine_model'] = 'Haas VF-2 (40-taper vertical mill)'
m.to_csv(out/'machines.csv', index=False)
print(ev.event_type.value_counts().to_dict(), 'rejected', len(rejected))
