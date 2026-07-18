"""
ISAC System Model for Smart City IoT Resource Allocation
==========================================================
System: 5G/6G ISAC BS serving heterogeneous IoT devices
Channel: Urban mmWave + sub-6GHz with path loss, shadowing, fading
Devices: Utility meters, environmental sensors, traffic cameras, safety devices

Parameterized with RWSCP real-world LoRaWAN telemetry from Prishtina
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple

# ─────────────────────────────────────────────────────────────
# Constants calibrated from RWSCP pilot & 3GPP TR 38.901
# ─────────────────────────────────────────────────────────────
SPEED_OF_LIGHT = 3e8
BOLTZMANN = 1.38e-23
NOISE_FIGURE_DB = 7.0          # Receiver noise figure
TEMPERATURE_K = 290            # Noise temperature
BANDWIDTH_TOTAL_HZ = 100e6    # 100 MHz system bandwidth (FR1)
NUM_SUBCARRIERS = 128          # OFDM subcarriers

# RWSCP-derived IoT traffic parameters (from all_meters_raw.csv analysis)
RWSCP_MEAN_INTERVAL_S = 3600       # ~1 hour mean inter-arrival
RWSCP_PAYLOAD_BYTES = 48           # Apator Ultrimis payload
RWSCP_RSSI_MEAN = -105            # dBm, from fleet_summary
RWSCP_SNR_STD = 3.5               # dB, measured variance


@dataclass
class DeviceProfile:
    """IoT device class with heterogeneous requirements."""
    name: str
    count: int
    payload_bytes: int
    interval_s: float          # Mean reporting interval
    qos_rate_bps: float        # Minimum required data rate
    qos_latency_ms: float      # Maximum tolerable latency
    sensing_priority: float    # 0-1, importance for ISAC sensing
    max_tx_power_dbm: float
    battery_capacity_mah: float
    
    
# Device profiles parameterized from RWSCP + smart city scenario
DEVICE_PROFILES = {
    'utility_meter': DeviceProfile(
        name='Utility Meter (RWSCP-type)',
        count=50, payload_bytes=48, interval_s=3600,
        qos_rate_bps=1e3, qos_latency_ms=5000,
        sensing_priority=0.3, max_tx_power_dbm=14,
        battery_capacity_mah=3600
    ),
    'env_sensor': DeviceProfile(
        name='Environmental Sensor',
        count=30, payload_bytes=64, interval_s=300,
        qos_rate_bps=5e3, qos_latency_ms=1000,
        sensing_priority=0.5, max_tx_power_dbm=20,
        battery_capacity_mah=2000
    ),
    'traffic_camera': DeviceProfile(
        name='Traffic Camera',
        count=10, payload_bytes=1024, interval_s=1,
        qos_rate_bps=5e6, qos_latency_ms=50,
        sensing_priority=0.9, max_tx_power_dbm=30,
        battery_capacity_mah=50000  # Mains-powered
    ),
    'safety_device': DeviceProfile(
        name='Public Safety Device',
        count=10, payload_bytes=256, interval_s=10,
        qos_rate_bps=1e5, qos_latency_ms=10,
        sensing_priority=1.0, max_tx_power_dbm=23,
        battery_capacity_mah=10000
    ),
}


@dataclass
class ISACSystemConfig:
    """ISAC system configuration."""
    carrier_freq_ghz: float = 3.5        # Sub-6 GHz (n78 band)
    bandwidth_hz: float = 100e6
    num_subcarriers: int = 128
    num_bs_antennas: int = 64            # Massive MIMO
    bs_tx_power_dbm: float = 46          # Macro BS
    cell_radius_m: float = 500
    num_mec_nodes: int = 3
    mec_compute_gflops: float = 100
    sensing_freq_range: Tuple[float, float] = (1.0, 100.0)  # Hz
    
    # Density scenarios
    density_multipliers = {'low': 0.5, 'medium': 1.0, 'high': 2.0}
    
    # Temporal profiles (fraction of peak load)
    temporal_profiles = {
        'off_peak': 0.3,
        'peak': 1.0, 
        'special_event': 1.5
    }


class UrbanChannelModel:
    """
    3GPP TR 38.901 Urban Micro (UMi) Street Canyon channel model.
    Incorporates path loss, log-normal shadowing, Rayleigh fading.
    """
    
    def __init__(self, fc_ghz: float = 3.5, scenario: str = 'UMi'):
        self.fc_ghz = fc_ghz
        self.fc_hz = fc_ghz * 1e9
        self.scenario = scenario
        
    def path_loss_db(self, distance_m: float, los: bool = True) -> float:
        """3GPP UMi path loss model."""
        d_3d = max(distance_m, 1.0)
        
        if los:
            # UMi-LOS: PL = 32.4 + 21*log10(d) + 20*log10(fc)
            pl = 32.4 + 21.0 * np.log10(d_3d) + 20.0 * np.log10(self.fc_ghz)
        else:
            # UMi-NLOS: PL = 35.3*log10(d) + 22.4 + 21.3*log10(fc)
            pl = 35.3 * np.log10(d_3d) + 22.4 + 21.3 * np.log10(self.fc_ghz)
            
        return pl
    
    def shadowing_db(self, los: bool = True) -> float:
        """Log-normal shadowing (sigma from 3GPP)."""
        sigma = 4.0 if los else 7.82
        return np.random.normal(0, sigma)
    
    def fading_linear(self) -> float:
        """Rayleigh fading (small-scale)."""
        return np.random.exponential(1.0)
    
    def get_channel_gain(self, distance_m: float, los_prob: float = None) -> float:
        """
        Compute channel gain in linear scale.
        Returns h^2 (channel power gain).
        """
        if los_prob is None:
            # UMi LOS probability: Pr(LOS) = min(18/d, 1) * (1 - exp(-d/36)) + exp(-d/36)
            d = max(distance_m, 1.0)
            los_prob = min(18.0/d, 1.0) * (1 - np.exp(-d/36.0)) + np.exp(-d/36.0)
        
        is_los = np.random.random() < los_prob
        
        pl_db = self.path_loss_db(distance_m, is_los)
        shadow_db = self.shadowing_db(is_los)
        fading = self.fading_linear()
        
        # Total channel gain (linear)
        total_loss_db = pl_db + shadow_db
        channel_gain = 10**(-total_loss_db / 10) * fading
        
        return channel_gain


class ISACSimulator:
    """
    Main ISAC system simulator.
    Evaluates 4 objectives for a given resource allocation decision.
    """
    
    def __init__(self, config: ISACSystemConfig = None, seed: int = 42):
        self.config = config or ISACSystemConfig()
        self.rng = np.random.RandomState(seed)
        self.channel = UrbanChannelModel(self.config.carrier_freq_ghz)
        
        # Noise power
        noise_power_w = BOLTZMANN * TEMPERATURE_K * self.config.bandwidth_hz
        noise_figure_linear = 10**(NOISE_FIGURE_DB / 10)
        self.noise_power_w = noise_power_w * noise_figure_linear
        self.noise_power_dbm = 10 * np.log10(self.noise_power_w * 1e3)
        
    def generate_device_positions(self, density: str = 'medium') -> dict:
        """Generate random device positions within cell."""
        mult = self.config.density_multipliers[density]
        positions = {}
        
        for dev_type, profile in DEVICE_PROFILES.items():
            n = int(profile.count * mult)
            # Uniform distribution within cell
            angles = self.rng.uniform(0, 2*np.pi, n)
            radii = self.config.cell_radius_m * np.sqrt(self.rng.uniform(0, 1, n))
            distances = np.maximum(radii, 10.0)  # Min 10m from BS
            positions[dev_type] = {
                'distances': distances,
                'count': n,
                'profile': profile
            }
            
        return positions
    
    def evaluate_allocation(
        self,
        power_alloc: np.ndarray,         # Per-device Tx power (dBm)
        sensing_freq: np.ndarray,         # Per-device sensing frequency (Hz)
        bw_alloc: np.ndarray,             # Per-device bandwidth fraction
        offload_ratio: np.ndarray,        # Per-device MEC offload ratio [0,1]
        positions: dict,
        temporal: str = 'peak'
    ) -> dict:
        """
        Evaluate 4 objectives for a given resource allocation.
        
        Returns dict with:
            - energy_consumption: Total energy (J) per time slot
            - sensing_accuracy: Mean sensing SINR satisfaction [0,1]
            - comm_reliability: Fraction of devices meeting QoS rate
            - avg_latency_ms: Average device latency
        """
        load_factor = self.config.temporal_profiles[temporal]
        
        total_energy_j = 0.0
        sensing_scores = []
        comm_satisfied = []
        latencies_ms = []
        
        idx = 0
        for dev_type, pos_info in positions.items():
            n = pos_info['count']
            profile = pos_info['profile']
            distances = pos_info['distances']
            
            for i in range(n):
                if idx >= len(power_alloc):
                    break
                    
                d = distances[i]
                p_tx_dbm = power_alloc[idx]
                sf = sensing_freq[idx]
                bw_frac = bw_alloc[idx]
                offload = offload_ratio[idx]
                
                # ── Channel gain ──
                h2 = self.channel.get_channel_gain(d)
                
                # ── Communication SINR ──
                p_tx_w = 10**((p_tx_dbm - 30) / 10)
                bw_hz = bw_frac * self.config.bandwidth_hz
                noise_w = BOLTZMANN * TEMPERATURE_K * bw_hz * 10**(NOISE_FIGURE_DB/10)
                
                # Array gain from massive MIMO
                array_gain = self.config.num_bs_antennas * 0.7  # 70% beamforming efficiency
                
                sinr_comm = (p_tx_w * h2 * array_gain) / noise_w
                rate_bps = bw_hz * np.log2(1 + sinr_comm)
                
                # ── Sensing SINR (radar return, two-way) ──
                bs_power_w = 10**((self.config.bs_tx_power_dbm - 30) / 10) * bw_frac
                rcs = 1.0  # Radar cross-section (m^2), nominal
                h2_sensing = self.channel.get_channel_gain(d)
                sinr_sensing = (bs_power_w * h2_sensing * rcs * array_gain**2) / (noise_w * d**2)
                
                # Sensing accuracy: sigmoid mapping of SINR to [0,1]
                sinr_sensing_db = 10 * np.log10(max(sinr_sensing, 1e-10))
                sensing_acc = 1.0 / (1.0 + np.exp(-0.5 * (sinr_sensing_db - 5)))
                sensing_scores.append(sensing_acc * profile.sensing_priority)
                
                # ── Communication reliability ──
                qos_met = 1.0 if rate_bps >= profile.qos_rate_bps * load_factor else 0.0
                comm_satisfied.append(qos_met)
                
                # ── Latency (transmission + processing + MEC offload) ──
                tx_time_ms = (profile.payload_bytes * 8 / max(rate_bps, 1)) * 1000
                proc_local_ms = profile.payload_bytes * 0.01 * (1 - offload)
                proc_mec_ms = profile.payload_bytes * 0.002 * offload + 2.0 * offload  # 2ms backhaul
                total_latency = tx_time_ms + proc_local_ms + proc_mec_ms
                latencies_ms.append(total_latency)
                
                # ── Energy consumption ──
                # Tx energy
                tx_duration_s = profile.payload_bytes * 8 / max(rate_bps, 1)
                tx_energy_j = p_tx_w * tx_duration_s
                
                # Sensing energy (BS-side, proportional to sensing freq)
                sensing_energy_j = bs_power_w * (sf / 100.0) * 0.001  # per measurement
                
                # Circuit energy
                circuit_power_w = 0.1  # 100 mW circuit power
                circuit_energy_j = circuit_power_w * tx_duration_s
                
                total_energy_j += (tx_energy_j + sensing_energy_j + circuit_energy_j) * load_factor
                
                idx += 1
        
        # Aggregate objectives
        n_total = idx
        if n_total == 0:
            return {'energy': 1e6, 'sensing': 0.0, 'reliability': 0.0, 'latency': 1e6}
        
        results = {
            'energy': total_energy_j,
            'sensing': np.mean(sensing_scores) if sensing_scores else 0.0,
            'reliability': np.mean(comm_satisfied) if comm_satisfied else 0.0,
            'latency': np.mean(latencies_ms) if latencies_ms else 1e6,
            'n_devices': n_total
        }
        
        return results
    
    def get_total_devices(self, density: str = 'medium') -> int:
        """Get total number of devices for a density scenario."""
        mult = self.config.density_multipliers[density]
        return sum(int(p.count * mult) for p in DEVICE_PROFILES.values())


if __name__ == '__main__':
    # Quick test
    sim = ISACSimulator(seed=42)
    positions = sim.generate_device_positions('medium')
    n = sim.get_total_devices('medium')
    print(f"Total devices (medium density): {n}")
    
    # Random allocation
    power = np.random.uniform(5, 23, n)
    sensing = np.random.uniform(1, 50, n)
    bw = np.random.uniform(0.005, 0.05, n)
    bw = bw / bw.sum()  # Normalize
    offload = np.random.uniform(0, 1, n)
    
    results = sim.evaluate_allocation(power, sensing, bw, offload, positions, 'peak')
    print(f"Results: {results}")
