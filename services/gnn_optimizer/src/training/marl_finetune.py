import os
import sys
import torch
import torch.optim as optim
import torch.nn.functional as F
import random
import numpy as np # [FIX]: Imported numpy
from tqdm import tqdm

# SYSTEM PATH FIX 
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.config import FileConfig, TrainConfig, SimConfig, GraphConfig, ModelConfig
from src.graphBuilder.sumo_manager import SumoManager
from src.graphBuilder.graph_builder import TrafficGraphBuilder
from src.models.hgat_core import RecurrentHGAT
from src.training.reward_function_actor_critic import calculate_reward # [FIX]: Use updated reward
from src.utils.evaluator import Evaluator

# CONFIGURATION 
SUMO_CONFIG = SimConfig.SUMO_CFG
SUMO_NET = SimConfig.NET_FILE
PRETRAINED_PATH = FileConfig.PRETRAINED_MODEL_PATH
FINAL_MODEL_PATH = FileConfig.FINAL_MARL_OLD_MODEL_PATH
PLOT_SAVE_DIR = FileConfig.PLOTS_DIR

# Training Hyperparameters
EPISODES = TrainConfig.MARL_EPISODES          
STEPS_PER_EPISODE = TrainConfig.MARL_STEPS_PER_EPISODE 
LEARNING_RATE = TrainConfig.MARL_LEARNING_RATE
GAMMA = TrainConfig.MARL_GAMMA       
EPSILON_START = TrainConfig.EPSILON_START   
EPSILON_END = TrainConfig.EPSILON_END    
EPSILON_DECAY = TrainConfig.EPSILON_DECAY  

def select_action(logits, epsilon):
    if random.random() < epsilon:
        num_actions = logits.size(1)
        return torch.randint(0, num_actions, (logits.size(0),))
    return torch.argmax(logits, dim=1)

def train_marl():
    print(" Starting MARL Fine-Tuning (Localized)...")
    
    manager = SumoManager(SUMO_CONFIG, use_gui=False)
    graph_builder = TrafficGraphBuilder(SUMO_NET)
    evaluator = Evaluator()
    
    manager.start()
    manager.step()
    snap = manager.get_snapshot()
    data = graph_builder.create_hetero_data(snap)
    manager.close()
    
    print(f" Loading Pre-trained weights from {PRETRAINED_PATH}...")
    model = RecurrentHGAT(
        hidden_channels=TrainConfig.HIDDEN_DIM, 
        out_channels=GraphConfig.NUM_SIGNAL_PHASES, 
        num_heads=ModelConfig.NUM_HEADS, 
        metadata=data.metadata()
    )
    
    if os.path.exists(FINAL_MODEL_PATH):
        print(f" Found existing MARL model at {FINAL_MODEL_PATH}. Resuming training...")
        try:
            model.load_state_dict(torch.load(FINAL_MODEL_PATH, weights_only=True))
            print(" Resumed from previous MARL checkpoint.")
        except Exception as e:
            print(f" Could not load MARL model ({e}). Trying SSL Pre-trained...")
            try:
                model.load_state_dict(torch.load(PRETRAINED_PATH, weights_only=True), strict=False)
                print(" Loaded SSL Pre-trained weights.")
            except:
                print(" No weights found. Training from SCRATCH.")
    else:
        print(f" No previous MARL run found. Loading SSL weights from {PRETRAINED_PATH}...")
        try:
            model.load_state_dict(torch.load(PRETRAINED_PATH, weights_only=True), strict=False)
            print(" Loaded SSL Pre-trained weights.")
        except:
            print(" Training from SCRATCH.")

    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    epsilon = EPSILON_START

    history_rewards = []
    history_queues = []
    history_losses = []
    
    ACTION_INTERVAL = 15
    
    # [FIX]: Make baselines arrays so they track history independently for each intersection
    running_reward_mean = np.zeros(graph_builder.num_intersections)
    running_reward_std = np.ones(graph_builder.num_intersections)
    
    for episode in range(1, EPISODES + 1):
        manager.start()
        hidden_state = None
        
        ep_reward = 0
        ep_loss = 0
        ep_queue_sum = 0
        # [FIX]: Array initialization
        interval_reward = np.zeros(graph_builder.num_intersections)
        
        running_reward_mean = running_reward_mean * 0.9 
        
        print(f"\n Episode {episode}/{EPISODES} (Epsilon: {epsilon:.2f})")
        
        for t in tqdm(range(STEPS_PER_EPISODE)):

            if t % ACTION_INTERVAL == 0:
                snapshot = manager.get_snapshot()
                data = graph_builder.create_hetero_data(snapshot)
                
                action_logits, _, hidden_state = model(data.x_dict, data.edge_index_dict, hidden_state)
                actions_indices = select_action(action_logits, epsilon)
                
                idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}
                actions_dict = {}
                
                for idx, val in enumerate(actions_indices):
                    if idx in idx_to_id:
                        model_action = val.item()
                        tls_id = idx_to_id[idx]
                        
                        sumo_phase = 0
                        if model_action == 0: sumo_phase = 0
                        elif model_action == 1: sumo_phase = 2 
                        else: sumo_phase = 0
                        
                        actions_dict[tls_id] = sumo_phase

                manager.apply_actions(actions_dict)

                if t > 0:
                    probs = F.softmax(action_logits, dim=1)
                    log_probs = torch.log(probs.gather(1, actions_indices.view(-1, 1)))
                    
                    # [FIX]: Advantage is now an array
                    advantage = interval_reward
                    
                    running_reward_mean = 0.95 * running_reward_mean + 0.05 * advantage
                    running_reward_std = 0.95 * running_reward_std + 0.05 * np.abs(advantage - running_reward_mean)
                    
                    scaled_advantage = (advantage - running_reward_mean) / (running_reward_std + 1e-8)
                    scaled_adv_tensor = torch.tensor(scaled_advantage, dtype=torch.float32).to(action_logits.device)
                    # Clamp array
                    scaled_adv_tensor = torch.clamp(scaled_adv_tensor, -2.0, 2.0)
                    
                    entropy = - (probs * torch.log(probs + 1e-9)).sum(dim=1).mean()
                    entropy_coef = 0.05
                    
                    # [FIX]: Element-wise multiplication so each agent gets its own advantage applied!
                    # log_probs is [num_nodes, 1], so we squeeze it to [num_nodes]
                    loss = -(log_probs.squeeze() * scaled_adv_tensor).mean() - (entropy_coef * entropy)
                    
                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                    
                    hidden_state = hidden_state.detach()
                    ep_loss += loss.item()
                    
                    # [FIX]: Reset array
                    interval_reward = np.zeros(graph_builder.num_intersections)

            manager.step()
            
            if t > 0:
                current_snap = manager.get_snapshot()
                # [FIX]: Localized reward update
                r_step_array = calculate_reward(current_snap, graph_builder)
                interval_reward += r_step_array
                ep_reward += np.sum(r_step_array)
                ep_queue_sum += sum([l['queue_length'] for l in current_snap['lanes'].values()])

        manager.close()
        
        epsilon = max(EPSILON_END, epsilon * EPSILON_DECAY)
        avg_loss = ep_loss / (STEPS_PER_EPISODE / ACTION_INTERVAL)
        avg_queue = ep_queue_sum / STEPS_PER_EPISODE
        
        history_rewards.append(ep_reward)
        history_queues.append(avg_queue)
        history_losses.append(avg_loss)
        
        print(f" Episode {episode} Done. Reward: {ep_reward:.2f} | Avg Queue: {avg_queue:.2f} | Avg Loss: {avg_loss:.4f}")

        if episode % TrainConfig.MARL_TESTING_EPISODES == 0:
            test_score = evaluate_model(model, graph_builder, episode)
        
        torch.save(model.state_dict(), FINAL_MODEL_PATH)

    print(" Generating MARL Plots...")
    evaluator.plot_marl_performance(history_rewards, history_queues, history_losses, save_dir=PLOT_SAVE_DIR)

    print(" MARL Fine-Tuning Complete!")

def evaluate_model(model, graph_builder, episode_num):

    print(f"\n Starting Evaluation (Episode {episode_num})...")
    eval_manager = SumoManager(SUMO_CONFIG, use_gui=False) 
    eval_manager.start()
    
    total_eval_reward = 0
    total_queue_len = 0
    steps = 0
    
    model.eval()
    hidden_state = None
    ACTION_INTERVAL = 15 
    
    try:
        for t in range(STEPS_PER_EPISODE):
            if t % ACTION_INTERVAL == 0:
                snapshot = eval_manager.get_snapshot()
                data = graph_builder.create_hetero_data(snapshot)
                
                with torch.no_grad():
                    action_logits,_, hidden_state = model(data.x_dict, data.edge_index_dict, hidden_state)
                    actions_indices = torch.argmax(action_logits, dim=1)
                    
                    idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}
                    actions_dict = {}
                    
                    for idx, val in enumerate(actions_indices):
                        if idx in idx_to_id:
                            model_action = val.item()
                            tls_id = idx_to_id[idx]
                            
                            sumo_phase = 0
                            if model_action == 0: sumo_phase = 0
                            elif model_action == 1: sumo_phase = 2 
                            else: sumo_phase = 0
                            
                            actions_dict[tls_id] = sumo_phase
                    
                eval_manager.apply_actions(actions_dict)
            
            eval_manager.step()
            
            next_snapshot = eval_manager.get_snapshot()
            # [FIX]: Array and sum
            reward_array = calculate_reward(next_snapshot, graph_builder)
            total_eval_reward += np.sum(reward_array)
            
            current_q = sum([info['queue_length'] for info in next_snapshot['lanes'].values()])
            total_queue_len += current_q
            steps += 1
            
    except Exception as e:
        print(f" Evaluation Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        eval_manager.close()
        model.train() 
        
    avg_reward = total_eval_reward / steps
    avg_queue = total_queue_len / steps
    
    print(f" Evaluation Result: Avg Reward = {avg_reward:.2f} | Avg Queue Length = {avg_queue:.2f} vehicles")
    return avg_reward

if __name__ == "__main__":
    train_marl()