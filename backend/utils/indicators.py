import pandas as pd
import logging

def calculate_rsi(prices: list, period: int = 14) -> float:
    """
    Calculate the Relative Strength Index (RSI) for a given list of prices.
    
    Args:
        prices (list): List of closing prices (ordered by time ascending).
        period (int): The RSI period (default 14).
        
    Returns:
        float: The latest RSI value, or None if insufficient data.
    """
    if not prices or len(prices) < period + 1:
        logging.warning(f"Not enough data for RSI calculation: {len(prices) if prices else 0} < {period + 1}")
        return None
        
    try:
        series = pd.Series(prices)
        delta = series.diff()
        
        # Calculate Gain and Loss
        # Note: This uses simple moving average (SMA) for RSI as per original implementation.
        # Standard RSI often uses Wilder's Smoothing (EMA), but we stick to original logic for compatibility.
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        
        # Handle division by zero (if loss is 0, RSI is 100)
        # Pandas handles inf, but we ensure robustness
        rsi = 100 - (100 / (1 + rs))
        
        # Get latest RSI
        current_rsi = rsi.iloc[-1]
        
        if pd.isna(current_rsi):
            return None
            
        return float(current_rsi)
        
    except Exception as e:
        logging.error(f"Error calculating RSI: {e}")
        return None
