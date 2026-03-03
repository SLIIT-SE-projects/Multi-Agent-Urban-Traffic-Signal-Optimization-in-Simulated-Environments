import os
import sys
import torch
import torch.optim as optim
import torch.nn.functional as F
import random
import numpy as np
from tqdm import tqdm

# SYSTEM PATH FIX 
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.config import FileConfig, TrainConfig, SimConfig, GraphConfig, ModelConfig
from src.graphBuilder.sumo_manager import SumoManager
from src.graphBuilder.graph_builder import TrafficGraphBuilder
from src.models.hgat_core import RecurrentHGAT
from src.training.reward_function_actor_critic import calculate_reward
from src.utils.evaluator import Evaluator

# CONFIGURATION 
SUMO_CONFIG = SimConfig.SUMO_CFG
SUMO_NET = SimConfig.NET_FILE
PRETRAINED_PATH = FileConfig.PRETRAINED_MODEL_PATH
FINAL_MODEL_PATH = FileConfig.FINAL_MARL_MODEL_PATH
PLOT_SAVE_DIR = FileConfig.PLOTS_DIR

# Training Hyperparameters
EPISODES = TrainConfig.MARL_EPISODES          # Total simulation runs for fine-tuning
STEPS_PER_EPISODE = TrainConfig.MARL_STEPS_PER_EPISODE # Steps per run
LEARNING_RATE = TrainConfig.MARL_LEARNING_RATE
GAMMA = TrainConfig.MARL_GAMMA       # Discount factor for future rewards
GAE_LAMBDA = TrainConfig.GAE_LAMBDA
PPO_EPSILON = TrainConfig.PPO_EPSILON
PPO_EPOCHS = TrainConfig.PPO_EPOCHS
ENTROPY_COEF = TrainConfig.ENTROPY_COEF 
VALUE_LOSS_COEF = TrainConfig.VALUE_LOSS_COEF

ROUTE_EASY = "simulation/routes_easy.xml"
ROUTE_MEDIUM = "simulation/routes_medium.xml"
ROUTE_HARD = "simulation/routes_hard.xml"
ACTIVE_ROUTE = "simulation/routes.rou.xml" 


class RolloutBuffer:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.states = []       
        self.actions = []      
        self.log_probs = []    
        self.rewards = []      
        self.values = []       
        self.dones = []        
        self.hidden_states = [] 

def compute_gae(buffer, next_value, gamma, lam):
    values = torch.tensor(np.array(buffer.values), dtype=torch.float32)
    next_value = torch.tensor(next_value, dtype=torch.float32)
    
    values = torch.cat([values, next_value.unsqueeze(0)], dim=0)
    
    # [FIX]: Removed unsqueeze(1) from rewards because it is now an array of [steps, num_intersections]
    rewards = torch.tensor(np.array(buffer.rewards), dtype=torch.float32)
    dones = torch.tensor(buffer.dones, dtype=torch.float32).unsqueeze(1) # Broadcast over agents
    
    advantages = []
    last_gae_lam = torch.zeros_like(values[0])
    
    num_steps = len(rewards)
    for t in reversed(range(num_steps)):
        non_terminal = 1.0 - dones[t]
        delta = rewards[t] + gamma * values[t+1] * non_terminal - values[t]
        last_gae_lam = delta + gamma * lam * non_terminal * last_gae_lam
        advantages.insert(0, last_gae_lam)
        
    advantages = torch.stack(advantages)
    return advantages, values[:-1] + advantages

def ppo_update(model, optimizer, buffer, advantages, returns):
    old_log_probs = torch.stack(buffer.log_probs).detach()
    old_actions = torch.stack(buffer.actions).detach()
    
    old_log_probs = old_log_probs.view(-1)
    old_actions = old_actions.view(-1)
    advantages = advantages.view(-1)
    returns = returns.view(-1)
    
    advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
    
    total_loss_sum = 0
    old_hidden_states = [h.detach() if h is not None else None for h in buffer.hidden_states]
    
    for _ in range(PPO_EPOCHS):
        new_log_probs_list = []
        new_values_list = []
        entropy_list = []
        
        for i, data in enumerate(buffer.states):
            h_in = old_hidden_states[i]
            logits, val, _ = model(data.x_dict, data.edge_index_dict, h_in, data.edge_attr_dict)
            probs = F.softmax(logits, dim=1)
            dist = torch.distributions.Categorical(probs)
            
            action_taken = buffer.actions[i]
            new_log_prob = dist.log_prob(action_taken)
            entropy = dist.entropy()
            
            new_log_probs_list.append(new_log_prob)
            new_values_list.append(val.squeeze())
            entropy_list.append(entropy)
            
        new_log_probs = torch.stack(new_log_probs_list).view(-1)
        new_values = torch.stack(new_values_list).view(-1)
        entropy = torch.stack(entropy_list).view(-1).mean()
        
        ratio = (new_log_probs - old_log_probs).exp()
        surr1 = ratio * advantages
        surr2 = torch.clamp(ratio, 1.0 - PPO_EPSILON, 1.0 + PPO_EPSILON) * advantages
        
        policy_loss = -torch.min(surr1, surr2).mean()
        value_loss = F.mse_loss(new_values, returns)
        
        loss = policy_loss + (VALUE_LOSS_COEF * value_loss) - (ENTROPY_COEF * entropy)
        
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
        optimizer.step()
        
        total_loss_sum += loss.item()

    return total_loss_sum / PPO_EPOCHS

def select_action(logits):
    probs = F.softmax(logits, dim=1)
    m = torch.distributions.Categorical(probs)
    action = m.sample()
    return action, m.log_prob(action)

def get_next_green_phase(current_phase, total_phases=4):
    """
    Advances to next GREEN phase, safely skipping yellow transitions.
    Standard SUMO 4-phase: 0=GreenNS, 1=YellowNS, 2=GreenEW, 3=YellowEW
    """
    next_phase = (current_phase + 1) % total_phases
    # Skip yellow (odd phases are typically yellow in standard SUMO setup)
    if next_phase % 2 != 0:
        next_phase = (next_phase + 1) % total_phases
    return next_phase


def apply_actions_unified(action_tensor, snapshot, idx_to_id, manager):
    """
    Single function used by BOTH training and evaluation.
    Guarantees identical behavior everywhere.
    action=0: keep current phase (do nothing)
    action=1: advance to next green phase
    """
    actions_dict = {}
    for idx, val in enumerate(action_tensor):
        if idx not in idx_to_id:
            continue
        tls_id = idx_to_id[idx]
        model_action = val.item()

        if model_action == 1:  # Switch
            current_phase = int(
                snapshot['intersections'][tls_id]['phase_index']
            )
            next_green = get_next_green_phase(current_phase)
            actions_dict[tls_id] = next_green
        # model_action == 0: do nothing, SUMO keeps current phase

    manager.apply_actions(actions_dict)

def sanity_check():
    print("=" * 50)
    print("RUNNING SANITY CHECK...")
    print("=" * 50)
    
    from src.config import GraphConfig, TrainConfig, ModelConfig
    
    # 1. Check config consistency
    assert GraphConfig.NUM_ACTIONS == 2, \
        f"NUM_ACTIONS should be 2, got {GraphConfig.NUM_ACTIONS}"
    assert GraphConfig.NUM_SIGNAL_PHASES == 4, \
        f"NUM_SIGNAL_PHASES should be 4, got {GraphConfig.NUM_SIGNAL_PHASES}"
    assert GraphConfig.INTERSECTION_INPUT_DIM == GraphConfig.NUM_SIGNAL_PHASES + 2, \
        f"INTERSECTION_INPUT_DIM mismatch!"
    print(f"✅ Config: NUM_ACTIONS={GraphConfig.NUM_ACTIONS}, "
          f"NUM_SIGNAL_PHASES={GraphConfig.NUM_SIGNAL_PHASES}, "
          f"INTERSECTION_INPUT_DIM={GraphConfig.INTERSECTION_INPUT_DIM}")

    # 2. Check model output shape
    manager = SumoManager(SUMO_CONFIG, use_gui=False)
    graph_builder = TrafficGraphBuilder(SUMO_NET)
    manager.start()
    manager.step()
    snap = manager.get_snapshot()
    data = graph_builder.create_hetero_data(snap)
    manager.close()

    model = RecurrentHGAT(
        hidden_channels=TrainConfig.HIDDEN_DIM,
        out_channels=GraphConfig.NUM_ACTIONS,
        num_heads=ModelConfig.NUM_HEADS,
        metadata=data.metadata()
    )

    with torch.no_grad():
        logits, value, hidden = model(
            data.x_dict, data.edge_index_dict, None, data.edge_attr_dict
        )

    n = graph_builder.num_intersections
    assert logits.shape == (n, 2), \
        f"❌ Logits shape wrong: expected ({n}, 2), got {logits.shape}"
    assert value.shape == (n, 1), \
        f"❌ Value shape wrong: expected ({n}, 1), got {value.shape}"
    assert hidden.shape == (n, TrainConfig.HIDDEN_DIM), \
        f"❌ Hidden shape wrong: expected ({n}, {TrainConfig.HIDDEN_DIM}), got {hidden.shape}"

    print(f"✅ Model output: logits={logits.shape}, "
          f"value={value.shape}, hidden={hidden.shape}")

    # 3. Check action function  ← REMOVED 'import torch' from here
    fake_actions = torch.tensor([0, 1, 0, 1])
    idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}
    print(f"✅ Action function: {len(idx_to_id)} intersections mapped")

    # 4. Check reward scale
    from src.training.reward_function_actor_critic import calculate_reward
    rewards = calculate_reward(snap, graph_builder)
    print(f"✅ Reward range: min={rewards.min():.3f}, "
          f"max={rewards.max():.3f}, mean={rewards.mean():.3f}")
    assert rewards.min() >= -2.0 and rewards.max() <= 1.0, \
        f"❌ Reward out of expected range [-2, 1]: {rewards}"

    print("=" * 50)
    print("✅ ALL CHECKS PASSED — Safe to start training")
    print("=" * 50)

def train_marl():
    print("Starting SOTA PPO MARL Training...")

    manager = SumoManager(SUMO_CONFIG, use_gui=False)
    graph_builder = TrafficGraphBuilder(SUMO_NET)
    evaluator = Evaluator()

    manager.start()
    manager.step()
    snap = manager.get_snapshot()
    data = graph_builder.create_hetero_data(snap)
    manager.close()

    model = RecurrentHGAT(
        hidden_channels=TrainConfig.HIDDEN_DIM,
        out_channels=GraphConfig.NUM_ACTIONS,  # Now = 2
        num_heads=ModelConfig.NUM_HEADS,
        metadata=data.metadata()
    )

    BEST_MODEL_PATH = FINAL_MODEL_PATH.replace(".pth", "_best.pth")

    if os.path.exists(PRETRAINED_PATH):
        print(f"Loading SSL weights from {PRETRAINED_PATH}...")
        model.load_state_dict(
            torch.load(PRETRAINED_PATH, weights_only=True), strict=False
        )

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = optim.lr_scheduler.StepLR(
        optimizer, step_size=TrainConfig.LR_STEP_SIZE, gamma=TrainConfig.LR_GAMMA   # Less aggressive than before
    )

    buffer = RolloutBuffer()
    history_rewards, history_queues, history_losses = [], [], []
    ACTION_INTERVAL = 20
    best_eval_reward = -float('inf')

    for episode in range(1, EPISODES + 1):

        # Curriculum
        if episode <= TrainConfig.EASY_UNTIL_EPISODE:
            source = ROUTE_EASY
        elif episode <= TrainConfig.MEDIUM_UNTIL_EPISODE:
            source = ROUTE_MEDIUM
        else:
            source = random.choice([ROUTE_MEDIUM, ROUTE_HARD, ROUTE_HARD])

        import shutil
        shutil.copy(source, ACTIVE_ROUTE)

        manager.start()
        hidden_state = None
        ep_reward = 0
        ep_queue_sum = 0
        ep_loss = 0
        interval_reward = np.zeros(graph_builder.num_intersections)
        step_counter = 0

        idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}
        current_lr = scheduler.get_last_lr()[0]
        print(f"\nEpisode {episode}/{EPISODES} | "
              f"Route: {os.path.basename(source)} | LR: {current_lr:.6f}")

        for t in tqdm(range(STEPS_PER_EPISODE)):

            if t % ACTION_INTERVAL == 0:
                snap = manager.get_snapshot()
                data = graph_builder.create_hetero_data(snap)

                with torch.no_grad():
                    h_in = hidden_state.clone() if hidden_state is not None else None
                    logits, value, hidden_state = model(
                        data.x_dict, data.edge_index_dict,
                        hidden_state, data.edge_attr_dict
                    )
                    action, log_prob = select_action(logits)

                # ── UNIFIED ACTION APPLICATION ────────────────────────────
                apply_actions_unified(action, snap, idx_to_id, manager)
                # ─────────────────────────────────────────────────────────

                if step_counter > 0:
                    buffer.rewards.append(interval_reward.copy())
                    buffer.dones.append(0)

                buffer.states.append(data)
                buffer.actions.append(action)
                buffer.log_probs.append(log_prob)
                buffer.values.append(value.detach().cpu().numpy().flatten())
                buffer.hidden_states.append(h_in)

                interval_reward = np.zeros(graph_builder.num_intersections)
                step_counter += 1

            manager.step()

            if t > 0:
                snap = manager.get_snapshot()
                r_array = calculate_reward(snap, graph_builder)
                interval_reward += r_array
                ep_reward += np.sum(r_array)
                ep_queue_sum += sum(
                    [l['queue_length'] for l in snap['lanes'].values()]
                )

        if len(buffer.states) > len(buffer.rewards):
            buffer.rewards.append(interval_reward.copy())
            buffer.dones.append(1)

        manager.close()

        if len(buffer.states) > 0:
            print("Updating PPO...")
            next_value = np.zeros(logits.shape[0])
            advantages, returns = compute_gae(
                buffer, next_value, GAMMA, GAE_LAMBDA
            )
            loss_val = ppo_update(
                model, optimizer, buffer, advantages, returns
            )
            ep_loss = loss_val
            print(f"Loss: {ep_loss:.4f} | Ep Reward: {ep_reward:.2f}")
            buffer.reset()

        scheduler.step()

        avg_queue = ep_queue_sum / STEPS_PER_EPISODE
        history_rewards.append(ep_reward)
        history_queues.append(avg_queue)
        history_losses.append(ep_loss)

        torch.save(model.state_dict(), FINAL_MODEL_PATH)
        evaluator.plot_marl_performance(
            history_rewards, history_queues, history_losses,
            save_dir=PLOT_SAVE_DIR
        )

        if episode % TrainConfig.MARL_TESTING_EPISODES == 0:
            current_eval_reward = evaluate_model(
                model, graph_builder, episode, idx_to_id
            )
            if current_eval_reward > best_eval_reward:
                print(f"NEW HIGH SCORE! ({current_eval_reward:.2f}). Saving.")
                best_eval_reward = current_eval_reward
                torch.save(model.state_dict(), BEST_MODEL_PATH)
            else:
                print(f"No improvement. Best: {best_eval_reward:.2f}")

# -------------------------------------------------------------
# [UPDATE 3]: The Flawless Evaluation Function
# -------------------------------------------------------------
def evaluate_model(model, graph_builder, episode_num, idx_to_id):
    print(f"\nStarting Evaluation (Episode {episode_num})...")

    import shutil
    shutil.copy(ROUTE_HARD, ACTIVE_ROUTE)

    eval_manager = SumoManager(SUMO_CONFIG, use_gui=False)
    eval_manager.start()

    total_eval_reward = 0
    total_queue_len = 0
    steps = 0
    model.eval()
    hidden_state = None
    ACTION_INTERVAL = 20

    try:
        for t in range(STEPS_PER_EPISODE):
            if t % ACTION_INTERVAL == 0:
                snapshot = eval_manager.get_snapshot()
                data = graph_builder.create_hetero_data(snapshot)

                with torch.no_grad():
                    action_logits, _, hidden_state = model(
                        data.x_dict, data.edge_index_dict,
                        hidden_state, data.edge_attr_dict
                    )
                    actions_indices = select_action(action_logits)[0]

                # ── SAME UNIFIED FUNCTION AS TRAINING ────────────────────
                apply_actions_unified(
                    actions_indices, snapshot, idx_to_id, eval_manager
                )
                # ─────────────────────────────────────────────────────────

            eval_manager.step()
            next_snapshot = eval_manager.get_snapshot()

            reward_array = calculate_reward(next_snapshot, graph_builder)
            total_eval_reward += np.sum(reward_array)
            total_queue_len += sum(
                [info['queue_length'] for info in next_snapshot['lanes'].values()]
            )
            steps += 1

    except Exception as e:
        print(f"Evaluation Failed: {e}")
    finally:
        eval_manager.close()
        model.train()

    avg_reward = total_eval_reward / steps
    avg_queue = total_queue_len / steps
    print(f"Avg Reward = {avg_reward:.2f} | Avg Queue = {avg_queue:.2f}")
    return avg_reward

if __name__ == "__main__":
    sanity_check()
    train_marl()