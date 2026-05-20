import simpy
import numpy as np
import pandas as pd
from data_processing import sample_value


# ---------------------------------------------------------------------------
# SIMULATION MODEL
# ---------------------------------------------------------------------------

class CafeSimulation:
    """SimPy discrete-event simulation for HUGO CAFE AS-IS model."""

    def __init__(self, env, fits, selected_dists, max_groups=350,
                 kitchen_cap=2, checkout_cap=1, waiter_cap=2):
        self.env = env
        self.fits = fits
        self.selected_dists = selected_dists
        self.max_groups = max_groups

        # SimPy resources
        self.kitchen = simpy.Resource(env, capacity=kitchen_cap)
        self.checkout = simpy.Resource(env, capacity=checkout_cap)
        self.waiters = simpy.Resource(env, capacity=waiter_cap)

        # Table configuration
        self.table_capacities = {
            'T1': 2, 'T2': 2, 'T3': 2, 'T4': 3, 'T5': 3
        }
        self.table_zones = {
            'T1': 'Terraza', 'T2': 'Terraza', 'T3': 'Terraza',
            'T4': 'Interior', 'T5': 'Interior'
        }
        self.table_states = {t: 'free' for t in self.table_capacities}
        self.table_occupants = {t: None for t in self.table_capacities}

        # Custom waiting queue
        self.waiting_queue = []

        # Logs & KPIs
        self.event_log = []
        self.kpis = {
            "groups_served": 0,
            "total_wait_time": 0.0,
            "total_system_time": 0.0,
            "wait_times": [],
            "system_times": [],
            "table_times": [],
            "waiter_wait_times": [],
            "kitchen_wait_times": [],
            "checkout_wait_times": [],
            "activity_times": {
                "toma_pedido": [], "comanda": [], "preparacion": [],
                "consumo": [], "pago": [], "reocupacion": []
            },
            "table_occupancies": {t: 0.0 for t in self.table_capacities},
            "exceptions_count": 0
        }

        # Resource busy intervals (for utilisation calc)
        self.kitchen_busy_intervals = []
        self.checkout_busy_intervals = []
        self.waiter_busy_intervals = []

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------
    def log_event(self, group_id, size, state, table=None,
                  wait_time=0.0, duration=0.0):
        self.event_log.append({
            "group_id": group_id,
            "size": size,
            "time": float(self.env.now),
            "state": state,
            "table": table,
            "wait_time": float(wait_time),
            "duration": float(duration)
        })

    # ------------------------------------------------------------------
    # Table allocation
    # ------------------------------------------------------------------
    def allocate_table(self, group_id, group_size):
        """Priority-based allocation following HUGO CAFE rules."""
        if group_size >= 3:
            compat = ['T4', 'T5']
        else:
            compat = ['T1', 'T2', 'T3', 'T4', 'T5']

        free = [t for t in compat if self.table_states[t] == 'free']

        if free:
            if group_size <= 2:
                terr = [t for t in free if t in ['T1', 'T2', 'T3']]
                sel = terr[0] if terr else free[0]
            else:
                sel = free[0]
            self.table_states[sel] = 'occupied'
            self.table_occupants[sel] = group_id
            return sel

        # No free table — enter queue
        evt = self.env.event()
        self.waiting_queue.append({
            "group_id": group_id, "size": group_size,
            "event": evt, "arrival_time": self.env.now
        })
        return evt

    def release_table(self, table_name):
        """Releases table and assigns to first compatible queued group."""
        self.table_states[table_name] = 'free'
        self.table_occupants[table_name] = None

        for i, req in enumerate(self.waiting_queue):
            ok = False
            if table_name in ['T4', 'T5']:
                ok = True
            elif table_name in ['T1', 'T2', 'T3'] and req["size"] <= 2:
                ok = True
            if ok:
                self.waiting_queue.pop(i)
                self.table_states[table_name] = 'occupied'
                self.table_occupants[table_name] = req["group_id"]
                req["event"].succeed(table_name)
                break

    # ------------------------------------------------------------------
    # Helper: sample from fit results
    # ------------------------------------------------------------------
    def _sample(self, col):
        """Sample a value for the given column using selected dist."""
        dist = self.selected_dists.get(col, 'empirical')
        fit = self.fits[col]

        if dist == 'empirical_discrete':
            params = fit.get('empirical_discrete', {})
            return sample_value('empirical_discrete', params)

        params = fit[dist].get('params', {}) if dist in fit else {}
        fb = None
        if 'empirical' in fit and 'params' in fit['empirical']:
            fb = fit['empirical']['params'].get('observed_values')
        return sample_value(dist, params, fb)

    # ------------------------------------------------------------------
    # Customer group process
    # ------------------------------------------------------------------
    def customer_group(self, group_id, size):
        arrival_time = self.env.now
        self.log_event(group_id, size, "arrival")

        # --- 1. Table assignment ---
        self.log_event(group_id, size, "assigning_table")
        alloc = self.allocate_table(group_id, size)

        if isinstance(alloc, simpy.Event):
            table = yield alloc
        else:
            table = alloc

        wait_table = self.env.now - arrival_time
        self.kpis["wait_times"].append(wait_table)
        self.kpis["total_wait_time"] += wait_table
        self.log_event(group_id, size, "assigned_table",
                       table=table, wait_time=wait_table)

        if size == 4:
            self.kpis["exceptions_count"] += 1

        table_start = self.env.now  # table occupancy starts here

        # --- 2. Toma de pedido + Comanda (WAITER REQUIRED) ---
        w_req_t = self.env.now
        with self.waiters.request() as wr:
            yield wr
            self.kpis["waiter_wait_times"].append(self.env.now - w_req_t)
            w_busy_start = self.env.now

            # Toma de pedido
            t_ped = self._sample('Toma_Pedido_min')
            self.log_event(group_id, size, "order_taking", table=table)
            yield self.env.timeout(t_ped)
            self.kpis["activity_times"]["toma_pedido"].append(t_ped)
            self.log_event(group_id, size, "order_taken",
                           table=table, duration=t_ped)

            # Comanda — waiter carries order to kitchen
            t_com = self._sample('Comanda_min')
            self.log_event(group_id, size, "order_sending", table=table)
            yield self.env.timeout(t_com)
            self.kpis["activity_times"]["comanda"].append(t_com)
            self.log_event(group_id, size, "order_sent",
                           table=table, duration=t_com)

            self.waiter_busy_intervals.append(
                (w_busy_start, self.env.now))
        # waiter released

        # --- 3. Preparacion (KITCHEN REQUIRED) ---
        k_req_t = self.env.now
        with self.kitchen.request() as kr:
            yield kr
            self.kpis["kitchen_wait_times"].append(self.env.now - k_req_t)
            k_start = self.env.now

            t_prep = self._sample('Preparacion_min')
            self.log_event(group_id, size, "order_preparing", table=table)
            yield self.env.timeout(t_prep)
            self.kitchen_busy_intervals.append((k_start, self.env.now))

        self.kpis["activity_times"]["preparacion"].append(t_prep)
        self.log_event(group_id, size, "prepared",
                       table=table, duration=t_prep)

        # --- 4. Consumo ---
        t_con = self._sample('Consumo_min')
        self.log_event(group_id, size, "eating", table=table)
        yield self.env.timeout(t_con)
        self.kpis["activity_times"]["consumo"].append(t_con)
        self.log_event(group_id, size, "eaten",
                       table=table, duration=t_con)

        # --- 5. Pago (CHECKOUT REQUIRED) ---
        co_req_t = self.env.now
        with self.checkout.request() as cor:
            yield cor
            self.kpis["checkout_wait_times"].append(self.env.now - co_req_t)
            co_start = self.env.now

            t_pago = self._sample('Pago_min')
            self.log_event(group_id, size, "paying", table=table)
            yield self.env.timeout(t_pago)
            self.checkout_busy_intervals.append((co_start, self.env.now))

        self.kpis["activity_times"]["pago"].append(t_pago)
        self.log_event(group_id, size, "paid",
                       table=table, duration=t_pago)

        # Customer leaves table
        table_occ_end = self.env.now
        system_time = table_occ_end - arrival_time   # customer perspective

        # --- 6. Reocupacion / limpieza (WAITER REQUIRED) ---
        w_req_t2 = self.env.now
        with self.waiters.request() as wr2:
            yield wr2
            self.kpis["waiter_wait_times"].append(self.env.now - w_req_t2)
            self.table_states[table] = 'cleaning'
            w_cl_start = self.env.now

            t_reoc = self._sample('Tiempo_Reocupacion_Mesa_min')
            self.log_event(group_id, size, "cleaning", table=table)
            yield self.env.timeout(t_reoc)
            self.waiter_busy_intervals.append((w_cl_start, self.env.now))

        self.kpis["activity_times"]["reocupacion"].append(t_reoc)
        self.log_event(group_id, size, "cleaned",
                       table=table, duration=t_reoc)

        # Table fully free now — includes cleaning duration
        table_time = self.env.now - table_start
        self.kpis["table_occupancies"][table] += table_time

        self.release_table(table)

        # --- Record metrics ---
        self.kpis["system_times"].append(system_time)
        self.kpis["table_times"].append(table_time)
        self.kpis["total_system_time"] += system_time
        self.kpis["groups_served"] += 1

        self.log_event(group_id, size, "left", table=table)


# ---------------------------------------------------------------------------
# ARRIVAL GENERATOR
# ---------------------------------------------------------------------------

def generate_arrivals(env, sim):
    group_id = 1
    ia_dist = sim.selected_dists.get('Interarribo_min', 'empirical')
    ia_fit = sim.fits['Interarribo_min']
    ia_params = ia_fit[ia_dist].get('params', {}) if ia_dist in ia_fit else {}
    ia_fb = None
    if 'empirical' in ia_fit and 'params' in ia_fit['empirical']:
        ia_fb = ia_fit['empirical']['params'].get('observed_values')

    grp_params = sim.fits['Grupo']['empirical_discrete']

    while group_id <= sim.max_groups:
        ia = sample_value(ia_dist, ia_params, ia_fb)
        yield env.timeout(ia)
        gs = sample_value('empirical_discrete', grp_params)
        env.process(sim.customer_group(group_id, gs))
        group_id += 1


# ---------------------------------------------------------------------------
# SINGLE RUN
# ---------------------------------------------------------------------------

def run_single_simulation(fits, selected_dists, max_groups=350,
                          kitchen_cap=2, checkout_cap=1, waiter_cap=2):
    env = simpy.Environment()
    sim = CafeSimulation(env, fits, selected_dists, max_groups,
                         kitchen_cap, checkout_cap, waiter_cap)
    env.process(generate_arrivals(env, sim))
    env.run()

    dur = env.now

    def _util(intervals, cap):
        if not intervals or dur == 0:
            return 0.0
        total = sum(e - s for s, e in intervals)
        return total / (dur * cap)

    k_util = _util(sim.kitchen_busy_intervals, kitchen_cap)
    co_util = _util(sim.checkout_busy_intervals, checkout_cap)
    w_util = _util(sim.waiter_busy_intervals, waiter_cap)

    table_utils = {t: (b / dur if dur > 0 else 0.0)
                   for t, b in sim.kpis["table_occupancies"].items()}

    _m = lambda lst: float(np.mean(lst)) if lst else 0.0

    return {
        "groups_served": sim.kpis["groups_served"],
        "sim_duration": float(dur),
        "avg_wait": _m(sim.kpis["wait_times"]),
        "max_wait": float(np.max(sim.kpis["wait_times"]))
                    if sim.kpis["wait_times"] else 0.0,
        "avg_system": _m(sim.kpis["system_times"]),
        "kitchen_utilization": float(k_util),
        "checkout_utilization": float(co_util),
        "waiter_utilization": float(w_util),
        "table_utilizations": table_utils,
        "exceptions_count": sim.kpis["exceptions_count"],
        "avg_waiter_wait": _m(sim.kpis["waiter_wait_times"]),
        "avg_kitchen_wait": _m(sim.kpis["kitchen_wait_times"]),
        "avg_checkout_wait": _m(sim.kpis["checkout_wait_times"]),
        "avg_table_time": _m(sim.kpis["table_times"]),
        "activity_averages": {
            k: _m(v) for k, v in sim.kpis["activity_times"].items()
        }
    }, sim.event_log


# ---------------------------------------------------------------------------
# MULTI-RUN
# ---------------------------------------------------------------------------

def run_multi_simulation(runs_count, fits, selected_dists, max_groups=350,
                         kitchen_cap=2, checkout_cap=1, waiter_cap=2):
    all_runs = []
    first_log = None

    for r in range(runs_count):
        summary, log = run_single_simulation(
            fits, selected_dists, max_groups,
            kitchen_cap, checkout_cap, waiter_cap)
        all_runs.append(summary)
        if r == 0:
            first_log = log

    df = pd.DataFrame([{
        "groups_served": s["groups_served"],
        "sim_duration": s["sim_duration"],
        "avg_wait": s["avg_wait"],
        "max_wait": s["max_wait"],
        "avg_system": s["avg_system"],
        "kitchen_util": s["kitchen_utilization"],
        "checkout_util": s["checkout_utilization"],
        "waiter_util": s["waiter_utilization"],
        "exceptions": s["exceptions_count"],
        "avg_waiter_wait": s["avg_waiter_wait"],
        "avg_kitchen_wait": s["avg_kitchen_wait"],
        "avg_checkout_wait": s["avg_checkout_wait"],
        "avg_table_time": s["avg_table_time"]
    } for s in all_runs])

    means = df.mean().to_dict()
    stds = df.std().fillna(0.0).to_dict()

    ci_95 = {}
    for col in df.columns:
        m = means[col]
        margin = 1.96 * (stds[col] / np.sqrt(runs_count)) \
            if runs_count > 1 else 0.0
        ci_95[col] = {
            "mean": float(m),
            "ci_lower": float(max(0.0, m - margin)),
            "ci_upper": float(m + margin),
            "min": float(df[col].min()),
            "max": float(df[col].max())
        }

    act = {}
    for a in ["toma_pedido", "comanda", "preparacion",
              "consumo", "pago", "reocupacion"]:
        act[a] = float(np.mean([s["activity_averages"][a]
                                for s in all_runs]))

    tbl_agg = {t: [] for t in ['T1', 'T2', 'T3', 'T4', 'T5']}
    for s in all_runs:
        for t in tbl_agg:
            tbl_agg[t].append(s["table_utilizations"][t])
    tbl_final = {t: float(np.mean(v)) for t, v in tbl_agg.items()}

    return {
        "runs_count": runs_count,
        "ci_95": ci_95,
        "activity_averages": act,
        "table_utilizations": tbl_final,
        "raw_runs": df.to_dict(orient="records")
    }, first_log
