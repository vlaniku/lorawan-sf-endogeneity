"""
DRL Agent for Online Pareto Policy Selection
==============================================
Stage 2 of the hybrid framework.
PPO agent that selects operating points from NSGA-III Pareto front
based on real-time network conditions.
"""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback

from isac_system_model import ISACSimulator, ISACSystemConfig


class ISACParetoEnv(gym.Env):
    """
    Gymnasium environment for Pareto-point selection.
    
    State:  [channel_quality, load_factor, avg_distance, device_density_norm,
             time_of_day_sin, time_of_day_cos, prev_energy, prev_sensing]
    Action: Index into Pareto front (discrete)
    Reward: Weighted satisfaction of 4 objectives under current conditions
    """
    
    def __init__(self, pareto_solutions, pareto_objectives, simulator, density='medium'):
        super().__init__()
        
        self.pareto_X = pareto_solutions
        self.pareto_F = pareto_objectives   # [energy, sensing, reliability, latency]
        self.n_solutions = len(pareto_solutions)
        self.simulator = simulator
        self.density = density
        self.n_devices = simulator.get_total_devices(density)
        
        # Action: select a Pareto solution index
        self.action_space = spaces.Discrete(self.n_solutions)
        
        # State: 8 environmental features
        self.observation_space = spaces.Box(
            low=-1.0, high=2.0, shape=(8,), dtype=np.float32
        )
        
        self.step_count = 0
        self.max_steps = 100
        self.prev_energy = 0.5
        self.prev_sensing = 0.5
        
        # Objective weights (can be adjusted for different priorities)
        self.weights = np.array([0.35, 0.25, 0.25, 0.15])  # energy, sensing, rel, latency
        
    def _get_state(self):
        """Generate current network state (simulated dynamics)."""
        t = self.step_count / self.max_steps
        
        # Simulate time-varying conditions
        channel_quality = 0.5 + 0.3 * np.sin(2 * np.pi * t) + np.random.normal(0, 0.1)
        load_factor = 0.3 + 0.7 * abs(np.sin(np.pi * t))  # Varies 0.3-1.0
        avg_distance = 200 + 100 * np.random.normal(0, 1)
        density_norm = {'low': 0.25, 'medium': 0.5, 'high': 1.0}[self.density]
        
        tod_sin = np.sin(2 * np.pi * t)
        tod_cos = np.cos(2 * np.pi * t)
        
        state = np.array([
            np.clip(channel_quality, 0, 1),
            np.clip(load_factor, 0.1, 1.5),
            np.clip(avg_distance / 500, 0, 1),
            density_norm,
            tod_sin,
            tod_cos,
            self.prev_energy,
            self.prev_sensing
        ], dtype=np.float32)
        
        return state
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.step_count = 0
        self.prev_energy = 0.5
        self.prev_sensing = 0.5
        return self._get_state(), {}
    
    def step(self, action):
        """Execute action (select Pareto point) and evaluate."""
        action = min(action, self.n_solutions - 1)
        
        # Get objectives for selected solution
        obj = self.pareto_F[action]
        energy, sensing, reliability, latency = obj
        
        # Apply environmental perturbation (conditions change)
        state = self._get_state()
        channel_q = state[0]
        load_f = state[1]
        
        # Perturb objectives based on conditions
        energy_actual = energy * (1.0 + 0.2 * (load_f - 0.5))
        sensing_actual = sensing * (0.8 + 0.4 * channel_q)
        reliability_actual = reliability * (0.7 + 0.3 * channel_q)
        latency_actual = latency * (1.0 + 0.5 * (load_f - 0.5))
        
        # Normalize objectives to [0, 1] for reward
        e_max = self.pareto_F[:, 0].max()
        l_max = self.pareto_F[:, 3].max()
        
        energy_norm = 1.0 - np.clip(energy_actual / max(e_max, 1e-6), 0, 1)
        sensing_norm = np.clip(sensing_actual, 0, 1)
        reliability_norm = np.clip(reliability_actual, 0, 1)
        latency_norm = 1.0 - np.clip(latency_actual / max(l_max, 1e-6), 0, 1)
        
        # Reward: weighted sum + bonus for meeting thresholds
        reward = (
            self.weights[0] * energy_norm +
            self.weights[1] * sensing_norm +
            self.weights[2] * reliability_norm +
            self.weights[3] * latency_norm
        )
        
        # Bonus for meeting QoS thresholds
        if sensing_actual >= 0.85:
            reward += 0.1
        if reliability_actual >= 0.90:
            reward += 0.1
        
        # Penalty for constraint violations
        if sensing_actual < 0.5:
            reward -= 0.2
        if reliability_actual < 0.5:
            reward -= 0.2
            
        self.prev_energy = energy_norm
        self.prev_sensing = sensing_norm
        self.step_count += 1
        
        terminated = self.step_count >= self.max_steps
        truncated = False
        
        info = {
            'energy': energy_actual,
            'sensing': sensing_actual,
            'reliability': reliability_actual,
            'latency': latency_actual,
            'action': action
        }
        
        return self._get_state(), reward, terminated, truncated, info


class TrainingCallback(BaseCallback):
    """Track rewards during training."""
    
    def __init__(self):
        super().__init__()
        self.episode_rewards = []
        self.current_rewards = []
        
    def _on_step(self):
        if len(self.locals.get('infos', [])) > 0:
            for info in self.locals['infos']:
                if 'episode' in info:
                    self.episode_rewards.append(info['episode']['r'])
        return True


def train_drl_agent(pareto_X, pareto_F, simulator, density='medium',
                    total_timesteps=50000, seed=42):
    """
    Train PPO agent for online Pareto selection.
    """
    print(f"\n{'='*60}")
    print(f"DRL Training: PPO agent for Pareto selection")
    print(f"Pareto solutions: {len(pareto_X)}, Timesteps: {total_timesteps}")
    print(f"{'='*60}")
    
    env = ISACParetoEnv(pareto_X, pareto_F, simulator, density)
    
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=256,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=0,
        seed=seed
    )
    
    callback = TrainingCallback()
    model.learn(total_timesteps=total_timesteps, callback=callback)
    
    print(f"Training completed.")
    
    return model, env, callback


def evaluate_drl_agent(model, env, n_episodes=50):
    """Evaluate trained DRL agent."""
    all_rewards = []
    all_metrics = {'energy': [], 'sensing': [], 'reliability': [], 'latency': []}
    action_dist = np.zeros(env.n_solutions)
    
    for ep in range(n_episodes):
        obs, _ = env.reset()
        episode_reward = 0
        ep_metrics = {'energy': [], 'sensing': [], 'reliability': [], 'latency': []}
        
        done = False
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            
            episode_reward += reward
            action_dist[info['action']] += 1
            for k in ep_metrics:
                ep_metrics[k].append(info[k])
        
        all_rewards.append(episode_reward)
        for k in all_metrics:
            all_metrics[k].append(np.mean(ep_metrics[k]))
    
    results = {
        'mean_reward': np.mean(all_rewards),
        'std_reward': np.std(all_rewards),
        'mean_energy': np.mean(all_metrics['energy']),
        'mean_sensing': np.mean(all_metrics['sensing']),
        'mean_reliability': np.mean(all_metrics['reliability']),
        'mean_latency': np.mean(all_metrics['latency']),
        'action_distribution': action_dist / action_dist.sum(),
        'all_rewards': all_rewards
    }
    
    return results
