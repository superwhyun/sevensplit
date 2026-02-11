"""
Migration script to transfer data from JSON files to SQLite database.
Run this once to migrate existing data.
"""

import json
import os
from database import get_db
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_ticker(ticker: str, json_file: str):
    """Migrate data for a single ticker from JSON to database"""
    if not os.path.exists(json_file):
        logging.info(f"No JSON file found for {ticker}, skipping...")
        return

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)

        db = get_db()
        logging.info(f"Migrating {ticker}...")

        # Migrate strategy config
        config = data.get('config', {})
        db.update_strategy_state(
            ticker,
            investment_per_split=config.get('investment_per_split', 100000.0),
            min_price=config.get('min_price', 0.0),
            max_price=config.get('max_price', 999999999.0),
            buy_rate=config.get('buy_rate', 0.005),
            sell_rate=config.get('sell_rate', 0.005),
            fee_rate=config.get('fee_rate', 0.0005),
            rebuy_strategy=config.get('rebuy_strategy', 'reset_on_clear'),
            is_running=data.get('is_running', False),
            next_split_id=data.get('next_split_id', 1),
            last_buy_price=data.get('last_buy_price'),
            last_sell_price=data.get('last_sell_price')
        )
        logging.info(f"  ✓ Migrated strategy config")

        # Migrate splits
        splits = data.get('splits', [])
        for split in splits:
            split_data = {
                'split_id': split['id'],
                'status': split['status'],
                'buy_price': split['buy_price'],
                'target_sell_price': split['target_sell_price'],
                'investment_amount': split['buy_amount'],
                'coin_volume': split.get('buy_volume', 0.0),
                'buy_order_id': split.get('buy_order_uuid'),
                'sell_order_id': split.get('sell_order_uuid')
            }
            db.add_split(ticker, split_data)
        logging.info(f"  ✓ Migrated {len(splits)} splits")

        # Migrate trade history
        trade_history = data.get('trade_history', [])
        for trade in trade_history:
            trade_data = {
                'split_id': trade['split_id'],
                'buy_price': trade['buy_price'],
                'sell_price': trade['sell_price'],
                'coin_volume': trade.get('volume', 0.0),
                'buy_amount': trade['buy_amount'],
                'sell_amount': trade['sell_amount'],
                'gross_profit': trade['gross_profit'],
                'total_fee': trade['total_fee'],
                'net_profit': trade['net_profit'],
                'profit_rate': trade['profit_rate'],
                'buy_order_id': None,
                'sell_order_id': None
            }
            # Parse timestamp if available
            if 'timestamp' in trade:
                try:
                    trade_data['timestamp'] = datetime.fromisoformat(trade['timestamp'])
                except:
                    pass

            db.add_trade(ticker, trade_data)
        logging.info(f"  ✓ Migrated {len(trade_history)} trades")

        logging.info(f"✓ Successfully migrated {ticker}")

    except Exception as e:
        logging.error(f"Failed to migrate {ticker}: {e}")


def main():
    """Main migration function"""
    print("\n" + "="*60)
    print("SevenSplit - JSON to Database Migration")
    print("="*60 + "\n")

    tickers = ["KRW-BTC", "KRW-ETH", "KRW-SOL"]
    backend_dir = os.path.dirname(os.path.abspath(__file__))

    for ticker in tickers:
        json_file = os.path.join(backend_dir, f"state_{ticker}.json")
        migrate_ticker(ticker, json_file)

    print("\n" + "="*60)
    print("Migration completed!")
    print("="*60)
    print("\nYou can now:")
    print("1. Backup the JSON files: mv backend/state_*.json backend/backup/")
    print("2. Start the bot normally: ./run-dev.sh")
    print("\nThe bot will now use the SQLite database (sevensplit.db)\n")


if __name__ == "__main__":
    main()
