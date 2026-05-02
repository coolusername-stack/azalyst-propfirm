import os
import json
import argparse
import glob
import yaml
import sys
from pathlib import Path
from datetime import datetime

# Add scanner dir to path so we can import BP modules
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from BP_paper_trader import PaperTrader

def merge_results(input_dir, output_file, config_path):
    all_signals = []
    all_indicators = {}
    total_scanned = 0
    
    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Find all chunk result files
    pattern = os.path.join(input_dir, "**", "chunk_result_*.json")
    files = glob.glob(pattern, recursive=True)
    
    print(f"Found {len(files)} chunk files to merge.")
    
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    all_signals.extend(data.get('signals', []))
                    all_indicators.update(data.get('indicators', {}))
                    total_scanned += data.get('watchlist_scanned', 0)
                else:
                    print(f"Warning: Unexpected format in {file_path}")
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
    # Initialize Paper Trader to get account state
    trader = PaperTrader(config)
    
    # Load state from data/paper_trader_state.json if it exists
    # In GitHub Actions, the 'data' folder is in the repo root.
    repo_root = SCRIPT_DIR.parent
    state_file = repo_root / "data" / "paper_trader_state.json"
    
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            trader.balance = state.get("balance", trader.balance)
            trader.initial_balance = state.get("initial_balance", trader.initial_balance)
            trader.closed_pnl_total = state.get("closed_pnl_total", 0.0)
            trader.total_trades = state.get("total_trades", 0)
            trader.winning_trades = state.get("winning_trades", 0)
            trader.losing_trades = state.get("losing_trades", 0)
            trader.peak_balance = state.get("peak_balance", trader.balance)
            trader.max_drawdown_pct = state.get("max_drawdown_pct", 0.0)
            trader.daily_pnl = state.get("daily_pnl", 0.0)
            trader.daily_trades = state.get("daily_trades", 0)
            trader.zone_memory = state.get("zone_memory", {})
            print(f"Restored trader state: ${trader.balance:,.2f}")
        except Exception as e:
            print(f"Could not load trader state: {e}")

    # Process signals through trader (if not already processed in chunks)
    # Note: In the parallel workflow, chunk runners already call submit_signal.
    # However, since they run in parallel, their state updates are lost.
    # We re-run submit_signal here on the merged list to ensure the central state is updated.
    auto_traded = 0
    for sig in all_signals:
        # Check if this signal was already traded in a chunk (it will have a paper_trade_id)
        # We re-submit to the CENTRAL trader state.
        pos_id = trader.submit_signal(sig)
        if pos_id:
            auto_traded += 1
            sig["paper_trade_id"] = pos_id

    # Build full result dict compatible with send_discord.py
    results = {
        "scan_time":         datetime.now().isoformat(),
        "scan_duration_sec": 0,
        "strategy":          config.get("active_strategy", "weekly"),
        "watchlist_scanned": total_scanned,
        "signals_found":     len(all_signals),
        "auto_traded":       auto_traded,
        "signals":           all_signals,
        "errors":            [],
        "account":           trader.get_account_summary(),
        "positions":         trader.get_open_positions(),
        "trade_history":     trader.get_trade_history(limit=100),
        "indicators":        all_indicators,
    }
    
    # Save final results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
        
    # Also save the updated trader state back to data/
    state_to_save = {
        "balance":          trader.balance,
        "initial_balance":  trader.initial_balance,
        "closed_pnl_total": trader.closed_pnl_total,
        "total_trades":     trader.total_trades,
        "winning_trades":   trader.winning_trades,
        "losing_trades":    trader.losing_trades,
        "peak_balance":     trader.peak_balance,
        "max_drawdown_pct": trader.max_drawdown_pct,
        "daily_pnl":        trader.daily_pnl,
        "daily_trades":     trader.daily_trades,
        "zone_memory":      trader.zone_memory,
        "saved_at":         datetime.now().isoformat(),
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state_to_save, f, indent=2)
        
    print(f"Merged {len(all_signals)} total signals into {output_file}")
    print(f"Final Account Balance: ${trader.balance:,.2f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--output-file', default='scan_results.json')
    parser.add_argument('--config', default='BP_config.yaml')
    args = parser.parse_args()
    
    merge_results(args.input_dir, args.output_file, args.config)
