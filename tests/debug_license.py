import os
import shutil
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.utils.utils_font import FONT_CONFIGS, _process_local_font

def debug_license_copy():
    config = FONT_CONFIGS["Pretendard"]
    font_dir = os.path.join(os.getcwd(), "assets", "fonts")
    
    print(f"Debug: Config type: {config.get('type')}")
    print(f"Debug: License path in config: {config.get('license_path')}")
    print(f"Debug: Source License Exists? {os.path.exists(config.get('license_path', ''))}")
    
    lic_dst = os.path.join(font_dir, "LICENSE_Pretendard.txt")
    print(f"Debug: Target License Path: {lic_dst}")
    print(f"Debug: Target Exists? {os.path.exists(lic_dst)}")
    
    # Run the function
    print("Running _process_local_font...")
    _process_local_font(config, font_dir)
    
    print(f"Debug: Target Exists After? {os.path.exists(lic_dst)}")

if __name__ == "__main__":
    debug_license_copy()
