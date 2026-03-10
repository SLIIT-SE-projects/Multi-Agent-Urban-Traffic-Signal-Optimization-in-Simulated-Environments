import torch.nn as nn
import torch.nn.functional as F
from src.config import ModelConfig

class BayesianDropout(nn.Module):
    
    def __init__(self, p=ModelConfig.DROPOUT_RATE):
        super().__init__()
        self.p = p
        self.force_on = False 

    def forward(self, x):
        # We use F.dropout and manually control the 'training' flag.
        # This forces dropout to apply if force_on is True, even if model.eval() was called.
        return F.dropout(x, p=self.p, training=self.training or self.force_on)

    def enable_mc_dropout(self):
        self.force_on = True

    def disable_mc_dropout(self):
        self.force_on = False