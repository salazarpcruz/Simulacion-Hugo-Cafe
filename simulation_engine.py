import simpy
import numpy as np
import pandas as pd
from data_processing import sample_value

class CafeSimulation:
    def __init__(self, env, fits, selected_dists, max_groups=350, kitchen_cap=2, checkout_cap=1):
        self.env = env
        self.fits = fits
        self.selected_dists = selected_dists
        self.max_groups = max_groups
        
        # SimPy Resources
        self.kitchen = simpy.Resource(env, capacity=kitchen_cap)
        self.checkout = simpy.Resource(env, capacity=checkout_cap)
        
        # Table States: 'free', 'occupied', 'cleaning'
        # Mesa capacities: T1:2, T2:2, T3:2, T4:3, T5:3
        self.table_capacities = {'T1': 2, 'T2': 2, 'T3': 2, 'T4': 3, 'T5': 3}
        self.table_zones = {'T1': 'Terraza', 'T2': 'Terraza', 'T3': 'Terraza', 'T4': 'Interior', 'T5': 'Interior'}
        self.table_states = {t: 'free' for t in self.table_capacities.keys()}
        self.table_occupants = {t: None for t in self.table_capacities.keys()} # tracks current GroupID
        
        # Waiting Queue for custom table allocation
        # Elements: {"group_id": int, "size": int, "event": simpy.Event, "arrival_time": float}
        self.waiting_queue = []
        
        # Logs and Metrics
        self.event_log = []
        self.kpis = {
            "groups_served": 0,
            "total_wait_time": 0.0,
            "total_system_time": 0.0,
            "wait_times": [],
            "system_times": [],
            "activity_times": {
                "toma_pedido": [],
                "comanda": [],
                "preparacion": [],
                "consumo": [],
                "pago": [],
                "reocupacion": []
            },
            "table_occupancies": {t: 0.0 for t in self.table_capacities.keys()}, # tracks cumulative time occupied
            "kitchen_busy_time": 0.0,
            "checkout_busy_time": 0.0,
            "exceptions_count": 0
        }
        
        # Resource active periods (to calculate utilization)
        self.kitchen_busy_intervals = [] # list of (start, end)
        self.checkout_busy_intervals = [] # list of (start, end)
        
    def log_event(self, group_id, size, state, table=None, wait_time=0.0, duration=0.0):
        """
        Adds an operational state change event to the timeline for the 2D layout animation.
        """
        self.event_log.append({
            "group_id": group_id,
            "size": size,
            "time": float(self.env.now),
            "state": state,
            "table": table,
            "wait_time": float(wait_time),
            "duration": float(duration)
        })

    def allocate_table(self, group_id, group_size):
        """
        Custom allocation logic based on HUGO CAFÉ rules:
        - T1, T2, T3 have capacity 2.
        - T4, T5 have capacity 3.
        - Groups of 3 can only go to T4 or T5.
        - Groups of 4 are operational exceptions and can only go to T4 or T5 (with extra chair).
        - Groups of 1 or 2 can sit anywhere, but prefer T1-T3 first.
        """
        arrival_time = self.env.now
        
        # Determine compatible tables
        if group_size >= 3:
            compatible_tables = ['T4', 'T5']
        else:
            # Group size 1 or 2
            compatible_tables = ['T1', 'T2', 'T3', 'T4', 'T5']
            
        # Check if any compatible table is free
        free_tables = [t for t in compatible_tables if self.table_states[t] == 'free']
        
        if free_tables:
            # If group size is 1 or 2, prefer T1-T3 (Terrace)
            if group_size <= 2:
                terrace_free = [t for t in free_tables if t in ['T1', 'T2', 'T3']]
                if terrace_free:
                    selected_table = terrace_free[0]
                else:
                    selected_table = free_tables[0]
            else:
                selected_table = free_tables[0]
                
            self.table_states[selected_table] = 'occupied'
            self.table_occupants[selected_table] = group_id
            return selected_table
            
        # No table available, enter queue
        alloc_event = self.env.event()
        self.waiting_queue.append({
            "group_id": group_id,
            "size": group_size,
            "event": alloc_event,
            "arrival_time": arrival_time
        })
        
        return alloc_event # will yield this event, which returns the allocated table name

    def release_table(self, table_name):
        """
        Releases a table and triggers allocation for the next compatible group in queue.
        """
        self.table_states[table_name] = 'free'
        self.table_occupants[table_name] = None
        
        # Check waiting queue for compatibility
        for i, request in enumerate(self.waiting_queue):
            group_size = request["size"]
            
            # Check if this group can sit at the freed table
            is_compatible = False
            if table_name in ['T4', 'T5']:
                is_compatible = True # T4, T5 fit any group size (1 to 4)
            elif table_name in ['T1', 'T2', 'T3'] and group_size <= 2:
                is_compatible = True # T1-T3 only fit size 1 or 2
                
            if is_compatible:
                # Allocate table to this group
                self.waiting_queue.pop(i)
                self.table_states[table_name] = 'occupied'
                self.table_occupants[table_name] = request["group_id"]
                
                # Wake up the group process
                request["event"].succeed(table_name)
                break

    def customer_group(self, group_id, size):
        """
        SimPy customer group process routine.
        Funnels through all restaurant activity phases.
        """
        arrival_time = self.env.now
        self.log_event(group_id, size, "arrival")
        
        # 1. Asignación de mesa (Waiting in queue if busy)
        self.log_event(group_id, size, "assigning_table")
        alloc_res = self.allocate_table(group_id, size)
        
        if isinstance(alloc_res, simpy.Event):
            # Block and wait for queue release
            table = yield alloc_res
        else:
            table = alloc_res
            
        wait_time = self.env.now - arrival_time
        self.kpis["wait_times"].append(wait_time)
        self.kpis["total_wait_time"] += wait_time
        
        self.log_event(group_id, size, "assigned_table", table=table, wait_time=wait_time)
        
        if size == 4:
            self.kpis["exceptions_count"] += 1
            
        # Track start time of table occupancy for utilization
        table_occupancy_start = self.env.now
        
        # 2. Toma de pedido (at table)
        dist = self.selected_dists.get('Toma_Pedido_min', 'empirical')
        params = self.fits['Toma_Pedido_min'][dist].get('params', {})
        fallback = self.fits['Toma_Pedido_min']['empirical']['params']['observed_values']
        toma_pedido_time = sample_value(dist, params, fallback)
        
        self.log_event(group_id, size, "order_taking", table=table)
        yield self.env.timeout(toma_pedido_time)
        self.kpis["activity_times"]["toma_pedido"].append(toma_pedido_time)
        self.log_event(group_id, size, "order_taken", table=table, duration=toma_pedido_time)
        
        # 3. Comanda (sending order to kitchen)
        dist = self.selected_dists.get('Comanda_min', 'empirical_discrete')
        params = self.fits['Comanda_min'].get('empirical_discrete', {})
        comanda_time = sample_value('empirical_discrete', params)
        
        self.log_event(group_id, size, "order_sending", table=table)
        yield self.env.timeout(comanda_time)
        self.kpis["activity_times"]["comanda"].append(comanda_time)
        self.log_event(group_id, size, "order_sent", table=table, duration=comanda_time)
        
        # 4. Preparación (Kitchen prep - occupies kitchen slot, group waits at table)
        dist = self.selected_dists.get('Preparacion_min', 'lognormal')
        params = self.fits['Preparacion_min'][dist].get('params', {})
        fallback = self.fits['Preparacion_min']['empirical']['params']['observed_values']
        preparacion_time = sample_value(dist, params, fallback)
        
        self.log_event(group_id, size, "order_preparing", table=table)
        kitchen_req_start = self.env.now
        with self.kitchen.request() as req:
            yield req
            # Kitchen preparation starts
            kitchen_start = self.env.now
            yield self.env.timeout(preparacion_time)
            kitchen_end = self.env.now
            self.kitchen_busy_intervals.append((kitchen_start, kitchen_end))
            
        self.kpis["activity_times"]["preparacion"].append(preparacion_time)
        self.log_event(group_id, size, "prepared", table=table, duration=preparacion_time)
        
        # 5. Consumo (eating food at table)
        dist = self.selected_dists.get('Consumo_min', 'lognormal')
        params = self.fits['Consumo_min'][dist].get('params', {})
        fallback = self.fits['Consumo_min']['empirical']['params']['observed_values']
        consumo_time = sample_value(dist, params, fallback)
        
        self.log_event(group_id, size, "eating", table=table)
        yield self.env.timeout(consumo_time)
        self.kpis["activity_times"]["consumo"].append(consumo_time)
        self.log_event(group_id, size, "eaten", table=table, duration=consumo_time)
        
        # 6. Pago (Checkout payment - occupies cashier, table remains occupied)
        dist = self.selected_dists.get('Pago_min', 'empirical')
        params = self.fits['Pago_min'][dist].get('params', {})
        fallback = self.fits['Pago_min']['empirical']['params']['observed_values']
        pago_time = sample_value(dist, params, fallback)
        
        self.log_event(group_id, size, "paying", table=table)
        with self.checkout.request() as req:
            yield req
            checkout_start = self.env.now
            yield self.env.timeout(pago_time)
            checkout_end = self.env.now
            self.checkout_busy_intervals.append((checkout_start, checkout_end))
            
        self.kpis["activity_times"]["pago"].append(pago_time)
        self.log_event(group_id, size, "paid", table=table, duration=pago_time)
        
        # Customer leaves the table (pago ends and they vacate)
        table_occupancy_end = self.env.now
        self.kpis["table_occupancies"][table] += (table_occupancy_end - table_occupancy_start)
        
        # 7. Reocupación de mesa (exit, clean, reset table for next group)
        dist = self.selected_dists.get('Tiempo_Reocupacion_Mesa_min', 'triangular')
        params = self.fits['Tiempo_Reocupacion_Mesa_min'][dist].get('params', {})
        fallback = self.fits['Tiempo_Reocupacion_Mesa_min']['empirical']['params']['observed_values']
        reocupacion_time = sample_value(dist, params, fallback)
        
        self.table_states[table] = 'cleaning'
        self.log_event(group_id, size, "cleaning", table=table)
        yield self.env.timeout(reocupacion_time)
        self.kpis["activity_times"]["reocupacion"].append(reocupacion_time)
        
        # Table reset finished, release table
        self.log_event(group_id, size, "cleaned", table=table, duration=reocupacion_time)
        self.release_table(table)
        
        # Record system metrics
        system_time = self.env.now - arrival_time
        self.kpis["system_times"].append(system_time)
        self.kpis["total_system_time"] += system_time
        self.kpis["groups_served"] += 1
        
        self.log_event(group_id, size, "left", table=table)

def generate_arrivals(env, sim_instance):
    """
    Generates customer groups based on interarrival distribution.
    """
    group_id = 1
    
    # Distributions for interarrivals and group sizes
    interarr_dist = sim_instance.selected_dists.get('Interarribo_min', 'empirical')
    interarr_params = sim_instance.fits['Interarribo_min'][interarr_dist].get('params', {})
    interarr_fallback = sim_instance.fits['Interarribo_min']['empirical']['params']['observed_values']
    
    group_params = sim_instance.fits['Grupo']['empirical_discrete']
    
    while group_id <= sim_instance.max_groups:
        # Sample next interarrival
        interarrival = sample_value(interarr_dist, interarr_params, interarr_fallback)
        yield env.timeout(interarrival)
        
        # Sample group size
        group_size = sample_value('empirical_discrete', group_params)
        
        # Start the customer group process thread
        env.process(sim_instance.customer_group(group_id, group_size))
        
        group_id += 1

def run_single_simulation(fits, selected_dists, max_groups=350, kitchen_cap=2, checkout_cap=1):
    """
    Orchestrates a single SimPy run.
    Returns calculated KPIs and the full detailed event log.
    """
    env = simpy.Environment()
    sim = CafeSimulation(env, fits, selected_dists, max_groups, kitchen_cap, checkout_cap)
    
    # Register arrival generator process
    env.process(generate_arrivals(env, sim))
    
    # Run the simulation until all threads finish
    env.run()
    
    sim_duration = env.now
    
    # Post-process utilization metrics
    # --- 1. Kitchen utilization ---
    # Merge overlapping kitchen busy intervals to get total kitchen active time
    kitchen_total_busy = 0.0
    if sim.kitchen_busy_intervals:
        # Sort intervals by start time
        sorted_intervals = sorted(sim.kitchen_busy_intervals)
        merged = [sorted_intervals[0]]
        for current in sorted_intervals[1:]:
            prev = merged[-1]
            if current[0] <= prev[1]:
                # Overlap, merge them
                merged[-1] = (prev[0], max(prev[1], current[1]))
            else:
                merged.append(current)
        # Sum the active durations, adjusted by parallel capacity
        # Since SimPy has 2 servers, we can also sum individual time spent / (sim_duration * kitchen_cap)
        # We will use sum(durations) / (sim_duration * capacity) for true operational utilization!
        kitchen_individual_total = sum(end - start for start, end in sim.kitchen_busy_intervals)
        kitchen_util = (kitchen_individual_total / (sim_duration * kitchen_cap)) if sim_duration > 0 else 0.0
    else:
        kitchen_util = 0.0
        
    # --- 2. Checkout utilization ---
    if sim.checkout_busy_intervals:
        checkout_individual_total = sum(end - start for start, end in sim.checkout_busy_intervals)
        checkout_util = (checkout_individual_total / (sim_duration * checkout_cap)) if sim_duration > 0 else 0.0
    else:
        checkout_util = 0.0
        
    # --- 3. Table utilizations ---
    table_utils = {}
    for table, busy in sim.kpis["table_occupancies"].items():
        # Utilization represents percentage of time the table holds a group + cleaning time
        # Let's add cleaning times too! Or utilize kpis['table_occupancies'] which captures group stay.
        # Let's count reocupación too since the table resource is held.
        # Actually, let's calculate active occupancy time divided by total simulation duration
        table_utils[table] = (busy / sim_duration) if sim_duration > 0 else 0.0
        
    # Standardise average wait and system times
    avg_wait = np.mean(sim.kpis["wait_times"]) if sim.kpis["wait_times"] else 0.0
    avg_system = np.mean(sim.kpis["system_times"]) if sim.kpis["system_times"] else 0.0
    max_wait = np.max(sim.kpis["wait_times"]) if sim.kpis["wait_times"] else 0.0
    
    # Store aggregated metrics
    summary = {
        "groups_served": sim.kpis["groups_served"],
        "sim_duration": float(sim_duration),
        "avg_wait": float(avg_wait),
        "max_wait": float(max_wait),
        "avg_system": float(avg_system),
        "kitchen_utilization": float(kitchen_util),
        "checkout_utilization": float(checkout_util),
        "table_utilizations": table_utils,
        "exceptions_count": sim.kpis["exceptions_count"],
        "activity_averages": {
            k: float(np.mean(v)) if v else 0.0 for k, v in sim.kpis["activity_times"].items()
        }
    }
    
    return summary, sim.event_log

def run_multi_simulation(runs_count, fits, selected_dists, max_groups=350, kitchen_cap=2, checkout_cap=1):
    """
    Runs multi-run simulations to evaluate statistical confidence in KPIs.
    """
    all_runs = []
    first_run_event_log = None
    
    for r in range(runs_count):
        summary, log = run_single_simulation(fits, selected_dists, max_groups, kitchen_cap, checkout_cap)
        all_runs.append(summary)
        if r == 0:
            first_run_event_log = log
            
    # Compile aggregated stats
    df_runs = pd.DataFrame([
        {
            "groups_served": r["groups_served"],
            "sim_duration": r["sim_duration"],
            "avg_wait": r["avg_wait"],
            "max_wait": r["max_wait"],
            "avg_system": r["avg_system"],
            "kitchen_util": r["kitchen_utilization"],
            "checkout_util": r["checkout_utilization"],
            "exceptions": r["exceptions_count"]
        } for r in all_runs
    ])
    
    # Calculate means and confidence intervals (95%)
    means = df_runs.mean().to_dict()
    stds = df_runs.std().fillna(0.0).to_dict()
    
    ci_95 = {}
    for col in df_runs.columns:
        # Standard error * critical value (1.96)
        margin = 1.96 * (stds[col] / np.sqrt(runs_count)) if runs_count > 1 else 0.0
        ci_95[col] = {
            "mean": float(means[col]),
            "ci_lower": float(max(0.0, means[col] - margin)),
            "ci_upper": float(means[col] + margin),
            "min": float(df_runs[col].min()),
            "max": float(df_runs[col].max())
        }
        
    # Aggregate average process times across all runs
    activity_data = {}
    for act in ["toma_pedido", "comanda", "preparacion", "consumo", "pago", "reocupacion"]:
        vals = [r["activity_averages"][act] for r in all_runs]
        activity_data[act] = float(np.mean(vals))
        
    # Aggregate table utilizations across all runs
    table_utils_agg = {t: [] for t in ['T1', 'T2', 'T3', 'T4', 'T5']}
    for r in all_runs:
        for t in table_utils_agg.keys():
            table_utils_agg[t].append(r["table_utilizations"][t])
            
    table_utils_final = {t: float(np.mean(v)) for t, v in table_utils_agg.items()}
    
    aggregated_results = {
        "runs_count": runs_count,
        "ci_95": ci_95,
        "activity_averages": activity_data,
        "table_utilizations": table_utils_final,
        "raw_runs": df_runs.to_dict(orient="records")
    }
    
    return aggregated_results, first_run_event_log
