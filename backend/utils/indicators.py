import logging

def calculate_rsi(prices: list, period: int = 14) -> float:
    """
    Calculate the Relative Strength Index (RSI) using Wilder's Smoothing method.
    This matches the official Upbit calculation guide.
    
    Args:
        prices (list): List of closing prices (ordered by time ascending).
        period (int): The RSI period (default 14).
        
    Returns:
        float: The latest RSI value, or None if insufficient data.
    """
    # Need at least period + 1 data points to calculate difference and initial average
    if not prices or len(prices) < period + 1:
        logging.warning(f"Not enough data for RSI calculation: {len(prices) if prices else 0} < {period + 1}")
        return None
        
    try:
        # 1. Calculate Deltas (Change Price)
        # prices[i] - prices[i-1]
        deltas = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i-1]
            deltas.append(diff)
            
        # 2. Separate Gains and Losses
        gains = []
        losses = []
        for change in deltas:
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
                
        # 3. Calculate Initial AU (Average Up) and AD (Average Down)
        # Simple Average for the first 'period'
        current_au = sum(gains[:period]) / period
        current_ad = sum(losses[:period]) / period
        
        # 4. Calculate Subsequent AU/AD using Wilder's Smoothing
        # Formula: (Previous AU * (period - 1) + Current Gain) / period
        for i in range(period, len(gains)):
            current_au = (current_au * (period - 1) + gains[i]) / period
            current_ad = (current_ad * (period - 1) + losses[i]) / period
            
        # 5. Calculate RS and RSI
        if current_ad == 0:
            return 100.0
            
        rs = current_au / current_ad
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
        
    except Exception as e:
        logging.error(f"Error calculating RSI: {e}")
        return None
