import os

# Base Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

class SimConfig:
    SUMO_BINARY = "sumo-gui"
    SIMULATION_FOLDER = os.path.join(PROJECT_ROOT, "simulation")
    NET_FILE = os.path.join(SIMULATION_FOLDER, "network.net.xml")
    ROUTE_FILE = os.path.join(SIMULATION_FOLDER, "routes.rou.xml")
    SUMO_CFG = os.path.join(SIMULATION_FOLDER, "scenario.sumocfg")
    
    STEP_LENGTH = 1.0  # Step size
    WARMUP_STEPS = 500 # Seconds to run before controlling
    MIN_GREEN_TIME = 5 # Safety constraint

class GraphConfig:
    NUM_ACTIONS = 2
    NUM_SIGNAL_PHASES = 4  # Fixed to 3 based on your map
    # [UPDATE]: Phases + time_to_switch + phase_duration
    INTERSECTION_INPUT_DIM = NUM_SIGNAL_PHASES + 2  
    LANE_INPUT_DIM = 3     # Queue + wait + Speed

    # [NEW] Add Edge Input Dimension for physical road properties
    EDGE_INPUT_DIM = 2     # Length, Speed Limit

class ModelConfig:
    NUM_HEADS = 2      # For GATConv
    DROPOUT_RATE = 0.15 # Uncertainty Mechanism
    USE_GRU = True     # Recurrent Wrapper

class TrainConfig:
    # DATA CONFIGURATION
    STEPS_TO_COLLECT = 3600  # 2 hours of simulation data

    # SSL TRAINING SETTINGS
    SSL_EPOCHS = 100
    HIDDEN_DIM = 64            # Up from 32 — needed for 2-layer GNN
    SSL_LEARNING_RATE = 0.001
    TRAIN_SPLIT = 0.8

    # MARL TRAINING SETTINGS
    MARL_EPISODES = 300
    MARL_STEPS_PER_EPISODE = 1000
    MARL_LEARNING_RATE = 1e-4
    ACTION_INTERVAL = 15    
    MARL_GAMMA = 0.99
    MARL_TESTING_EPISODES = 10  

    # PPO HYPERPARAMETERS 
    PPO_EPOCHS = 6        # How many times to train on the same batch
    GAE_LAMBDA = 0.95     # Generalized Advantage Estimation smoothing
    PPO_EPSILON = 0.15     # Clipping range 
    ENTROPY_COEF = 0.08   # Bonus for exploration
    VALUE_LOSS_COEF = 0.5 # Weight of the Critic's loss

    # Epsilon Greedy
    EPSILON_START = 1.0
    EPSILON_END = 0.05
    EPSILON_DECAY = 0.90

    # Reward Weights
    W_QUEUE = 0.8
    W_WAIT = 0.5

    # LR Scheduler
    LR_STEP_SIZE = 80
    LR_GAMMA = 0.6

    # Curriculum
    EASY_UNTIL_EPISODE = 30
    MEDIUM_UNTIL_EPISODE = 100

    # INFERENCE & SAFETY
    UNCERTAINTY_THRESHOLD = 0.05
    MC_SAMPLES = 20

class FileConfig:
    EXPERIMENTS_FOLDER = os.path.join(PROJECT_ROOT, "experiments")
    RAW_DATA_DIR = os.path.join(EXPERIMENTS_FOLDER, "raw_data")
    DATASET_PATH = os.path.join(RAW_DATA_DIR, "traffic_data_1hr.pt")

    MODELS_DIR = os.path.join(EXPERIMENTS_FOLDER, "saved_models")
    PRETRAINED_MODEL_PATH = os.path.join(MODELS_DIR, "pretrained_gnn.pth")
    FINAL_MARL_MODEL_PATH = os.path.join(MODELS_DIR, "final_marl_model.pth")
    FINAL_MARL_OLD_MODEL_PATH = os.path.join(MODELS_DIR, "reinforce_model.pth")

    PLOTS_DIR = os.path.join(EXPERIMENTS_FOLDER, "plots")