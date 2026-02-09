import torch
from src.models.hgat_core import RecurrentHGAT
from src.config import ModelConfig

def test_uncertainty():
    print("--- Starting Uncertainty Verification ---")
    
    # 1. Setup Dummy Data
    hidden_dim = 64
    num_heads = 4
    metadata = (['lane', 'intersection'], 
                [('lane', 'part_of', 'intersection'), 
                 ('intersection', 'adjacent_to', 'intersection'),
                 ('lane', 'feeds_into', 'lane')])
    
    # Initialize Model
    model = RecurrentHGAT(hidden_channels=hidden_dim, out_channels=4, num_heads=num_heads, metadata=metadata)
    model.eval() # Set to evaluation mode (standard behavior)

    # Create dummy input
    x_dict = {
        'lane': torch.randn(10, 10),       # 10 lanes, 10 features
        'intersection': torch.randn(2, 10) # 2 intersections, 10 features
    }
    edge_index_dict = {
        ('lane', 'part_of', 'intersection'): torch.tensor([[0, 1], [0, 1]]),
        ('intersection', 'adjacent_to', 'intersection'): torch.tensor([[0, 1], [1, 0]]),
        ('lane', 'feeds_into', 'lane'): torch.tensor([[0, 1], [1, 2]])
    }

    # 2. Test Standard Inference (Should be DETERMINISTIC)
    print("\n[Test 1] Standard Inference (Expected: Identical outputs)")
    model.mc_dropout.disable_mc_dropout()
    
    out1, _, _ = model(x_dict, edge_index_dict)
    out2, _, _ = model(x_dict, edge_index_dict)
    
    if torch.allclose(out1, out2):
        print("✅ SUCCESS: Standard inference is deterministic.")
    else:
        print("❌ FAIL: Standard inference produced different results!")

    # 3. Test Uncertainty Inference (Should be STOCHASTIC)
    print("\n[Test 2] MC Dropout Inference (Expected: Different outputs)")
    model.mc_dropout.enable_mc_dropout()
    
    out_samples = []
    for i in range(5):
        logits, _, _ = model(x_dict, edge_index_dict)
        out_samples.append(logits)
        print(f"  Sample {i+1} Mean: {logits.mean().item():.4f}")

    # Check variance
    stack = torch.stack(out_samples)
    variance = stack.var(dim=0).mean().item()
    
    if variance > 0.0001:
        print(f"✅ SUCCESS: Model produced variance (Var: {variance:.6f}). Uncertainty is active.")
    else:
        print("❌ FAIL: Model outputs are identical. Dropout is NOT working in the policy head.")

if __name__ == "__main__":
    test_uncertainty()