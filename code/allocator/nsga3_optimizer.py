"""
NSGA-III Multi-Objective Optimizer for ISAC Resource Allocation
================================================================
Stage 1 of the hybrid framework.
4 objectives: minimize energy, maximize sensing, maximize reliability, minimize latency
"""

import numpy as np
from pymoo.core.problem import Problem
from pymoo.algorithms.moo.nsga3 import NSGA3
from pymoo.util.ref_dirs import get_reference_directions
from pymoo.optimize import minimize as pymoo_minimize
from pymoo.termination import get_termination
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.indicators.hv import HV

from isac_system_model import ISACSimulator, ISACSystemConfig, DEVICE_PROFILES
import time


class ISACResourceProblem(Problem):
    """
    4-objective ISAC resource allocation problem for pymoo.
    
    Decision variables per device:
        - tx_power (dBm): [0, max_tx_power]
        - sensing_freq (Hz): [1, 100]
        - bw_fraction: [0.001, 0.1]
        - offload_ratio: [0, 1]
    
    Objectives (all minimized by pymoo convention):
        f1: Energy consumption (minimize)
        f2: -Sensing accuracy (maximize → minimize negative)
        f3: -Communication reliability (maximize → minimize negative)
        f4: Average latency (minimize)
    """
    
    def __init__(self, simulator: ISACSimulator, density: str = 'medium',
                 temporal: str = 'peak', seed: int = 42):
        self.simulator = simulator
        self.density = density
        self.temporal = temporal
        self.n_devices = simulator.get_total_devices(density)
        
        # Fix positions for consistent evaluation
        np.random.seed(seed)
        self.positions = simulator.generate_device_positions(density)
        
        n_var = self.n_devices * 4  # 4 variables per device
        
        # Bounds: scale BW upper limit to avoid infeasible constraint
        bw_upper = min(0.1, 0.8 / self.n_devices)
        xl = np.tile([0.0, 1.0, 0.0005, 0.0], self.n_devices)
        xu = np.tile([23.0, 100.0, bw_upper, 1.0], self.n_devices)
        
        super().__init__(
            n_var=n_var,
            n_obj=4,
            n_ieq_constr=1,  # BW sum ≤ 1
            xl=xl,
            xu=xu
        )
    
    def _evaluate(self, X, out, *args, **kwargs):
        """Evaluate population."""
        pop_size = X.shape[0]
        F = np.zeros((pop_size, 4))
        G = np.zeros((pop_size, 1))
        
        for i in range(pop_size):
            x = X[i]
            n = self.n_devices
            
            power = x[0::4][:n]
            sensing = x[1::4][:n]
            bw = x[2::4][:n]
            offload = x[3::4][:n]
            
            # Constraint: total BW ≤ 1
            bw_sum = bw.sum()
            G[i, 0] = bw_sum - 1.0  # ≤ 0
            
            # Normalize BW if over-allocated
            if bw_sum > 1.0:
                bw = bw / bw_sum
            
            results = self.simulator.evaluate_allocation(
                power, sensing, bw, offload, self.positions, self.temporal
            )
            
            F[i, 0] = results['energy']           # Minimize
            F[i, 1] = -results['sensing']          # Maximize → minimize negative
            F[i, 2] = -results['reliability']      # Maximize → minimize negative
            F[i, 3] = results['latency']           # Minimize
        
        out["F"] = F
        out["G"] = G


def run_nsga3_optimization(
    density: str = 'medium',
    temporal: str = 'peak',
    pop_size: int = 120,
    n_gen: int = 150,
    seed: int = 42
) -> dict:
    """
    Run NSGA-III optimization for a given scenario.
    Returns Pareto front and performance metrics.
    """
    print(f"\n{'='*60}")
    print(f"NSGA-III Optimization: density={density}, temporal={temporal}")
    print(f"Population: {pop_size}, Generations: {n_gen}")
    print(f"{'='*60}")
    
    config = ISACSystemConfig()
    simulator = ISACSimulator(config, seed=seed)
    
    problem = ISACResourceProblem(simulator, density, temporal, seed)
    print(f"Devices: {problem.n_devices}, Variables: {problem.n_var}")
    
    # Reference directions for 4 objectives
    ref_dirs = get_reference_directions("das-dennis", 4, n_partitions=6)
    print(f"Reference directions: {len(ref_dirs)}")
    
    algorithm = NSGA3(
        pop_size=pop_size,
        ref_dirs=ref_dirs,
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        seed=seed
    )
    
    termination = get_termination("n_gen", n_gen)
    
    t_start = time.time()
    res = pymoo_minimize(
        problem,
        algorithm,
        termination,
        seed=seed,
        verbose=False
    )
    t_elapsed = time.time() - t_start
    
    print(f"Optimization completed in {t_elapsed:.1f}s")
    
    if res.F is None:
        # Fallback: use last generation's population
        print("Warning: No feasible Pareto front. Using best population members.")
        pop_F = np.array([ind.F for ind in res.pop if ind.F is not None])
        pop_X = np.array([ind.X for ind in res.pop if ind.X is not None])
        if len(pop_F) == 0:
            raise ValueError("No valid solutions found")
        # Take top solutions by weighted sum
        weights = np.array([0.3, 0.25, 0.25, 0.2])
        scores = (pop_F * weights).sum(axis=1)
        top_k = min(20, len(scores))
        top_idx = np.argsort(scores)[:top_k]
        pareto_F_raw = pop_F[top_idx]
        pareto_X_raw = pop_X[top_idx]
    else:
        pareto_F_raw = res.F
        pareto_X_raw = res.X
    
    print(f"Pareto front solutions: {len(pareto_F_raw)}")
    
    # Convert back to original objective scale
    pareto_F = pareto_F_raw.copy()
    pareto_F[:, 1] = -pareto_F[:, 1]  # Sensing (back to maximize)
    pareto_F[:, 2] = -pareto_F[:, 2]  # Reliability (back to maximize)
    
    # Compute hypervolume
    ref_point = np.array([1.0, 0.0, 0.0, 100.0])  # Worst case reference
    
    return {
        'pareto_F': pareto_F,
        'pareto_X': pareto_X_raw,
        'n_solutions': len(pareto_F),
        'time_s': t_elapsed,
        'n_devices': problem.n_devices,
        'density': density,
        'temporal': temporal,
        'history': res.history if hasattr(res, 'history') else None
    }


def run_baseline_allocations(density='medium', temporal='peak', seed=42):
    """Run baseline allocation schemes for comparison."""
    config = ISACSystemConfig()
    simulator = ISACSimulator(config, seed=seed)
    positions = simulator.generate_device_positions(density)
    n = simulator.get_total_devices(density)
    
    baselines = {}
    
    # 1. Equal allocation
    power_eq = np.full(n, 15.0)
    sensing_eq = np.full(n, 50.0)
    bw_eq = np.full(n, 1.0/n)
    offload_eq = np.full(n, 0.5)
    res = simulator.evaluate_allocation(power_eq, sensing_eq, bw_eq, offload_eq, positions, temporal)
    baselines['Equal Allocation'] = res
    
    # 2. Max-rate greedy (max power, max BW)
    power_max = np.full(n, 23.0)
    sensing_max = np.full(n, 100.0)
    bw_max = np.full(n, 1.0/n)
    offload_max = np.full(n, 0.0)
    res = simulator.evaluate_allocation(power_max, sensing_max, bw_max, offload_max, positions, temporal)
    baselines['Max-Rate Greedy'] = res
    
    # 3. Energy-min (minimum power)
    power_min = np.full(n, 5.0)
    sensing_min = np.full(n, 10.0)
    bw_min = np.full(n, 1.0/n)
    offload_min = np.full(n, 1.0)  # Full offload
    res = simulator.evaluate_allocation(power_min, sensing_min, bw_min, offload_min, positions, temporal)
    baselines['Energy-Min'] = res
    
    # 4. Random allocation (average of 10 runs)
    energy_list, sens_list, rel_list, lat_list = [], [], [], []
    for s in range(10):
        np.random.seed(s + 100)
        power_r = np.random.uniform(5, 23, n)
        sensing_r = np.random.uniform(1, 100, n)
        bw_r = np.random.uniform(0.001, 0.1, n)
        bw_r = bw_r / bw_r.sum()
        offload_r = np.random.uniform(0, 1, n)
        res = simulator.evaluate_allocation(power_r, sensing_r, bw_r, offload_r, positions, temporal)
        energy_list.append(res['energy'])
        sens_list.append(res['sensing'])
        rel_list.append(res['reliability'])
        lat_list.append(res['latency'])
    baselines['Random'] = {
        'energy': np.mean(energy_list),
        'sensing': np.mean(sens_list),
        'reliability': np.mean(rel_list),
        'latency': np.mean(lat_list)
    }
    
    return baselines


if __name__ == '__main__':
    result = run_nsga3_optimization(density='medium', temporal='peak', 
                                     pop_size=92, n_gen=100, seed=42)
    print(f"\nPareto front shape: {result['pareto_F'].shape}")
    print(f"Energy range: [{result['pareto_F'][:,0].min():.4f}, {result['pareto_F'][:,0].max():.4f}]")
    print(f"Sensing range: [{result['pareto_F'][:,1].min():.4f}, {result['pareto_F'][:,1].max():.4f}]")
    print(f"Reliability range: [{result['pareto_F'][:,2].min():.4f}, {result['pareto_F'][:,2].max():.4f}]")
    print(f"Latency range: [{result['pareto_F'][:,3].min():.4f}, {result['pareto_F'][:,3].max():.4f}]")
