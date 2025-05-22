#!/usr/bin/env python3
"""
Update Spotify Burner config.json files with the CDBurnerXP path.
This script updates both the portable config under PortableData and the default config.json.
"""
import json
import os
import sys

# Determine workspace root (script's directory)
script_dir = os.path.abspath(os.path.dirname(__file__))

# Paths to config files
def portable_config():
    return os.path.join(script_dir, 'PortableData', 'config.json')
def default_config():
    return os.path.join(script_dir, 'config.json')

configs = []
# Portable config always exists
p_cfg = portable_config()
if os.path.exists(p_cfg):
    configs.append(p_cfg)
# Default config may exist
d_cfg = default_config()
if os.path.exists(d_cfg):
    configs.append(d_cfg)

# Get CDBurnerXP path from environment variable
burner_path = os.environ.get('CDBURNERXP_PATH', '')
if not burner_path:
    print('Warning: CDBURNERXP_PATH environment variable is not set')

for cfg_path in configs:
    try:
        print(f'Updating {cfg_path}')
        with open(cfg_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f'Failed to load {cfg_path}: {e}', file=sys.stderr)
        continue
    # Ensure burn_settings
    bs = data.setdefault('burn_settings', {})
    bs['cdburnerxp_path'] = burner_path
    # Write back
    try:
        with open(cfg_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f'Successfully updated {cfg_path}')
    except Exception as e:
        print(f'Failed to write {cfg_path}: {e}', file=sys.stderr)
