import torch
import sys

print(f"Python version: {sys.version}")
print(f"PyTorch version: {torch.__version__}")
print("-" * 20)

if torch.cuda.is_available():
    print("✅ GPU IS AVAILABLE!")
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version: {torch.version.cuda}")
else:
    print("❌ GPU IS NOT AVAILABLE.")
    print("PyTorch is running on CPU.")
