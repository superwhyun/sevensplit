def calculate_rsi_wilder(prices, period=14):
    if len(prices) <= period: return [None] * len(prices)
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    avg_gain = sum([max(d, 0) for d in deltas[:period]]) / period
    avg_loss = sum([max(-d, 0) for d in deltas[:period]]) / period
    res = [None] * (period + 1)
    res[-1] = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + max(deltas[i], 0)) / period
        avg_loss = (avg_loss * (period - 1) + max(-deltas[i], 0)) / period
        rsi = 100 - (100 / (1 + (avg_gain / avg_loss))) if avg_loss != 0 else 100
        res.append(rsi)
    return res

def calculate_rsi_sma(prices, period=14):
    if len(prices) <= period: return [None] * len(prices)
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    res = [None] * (period + 1)
    for i in range(period, len(deltas) + 1):
        window = deltas[i-period:i]
        gain = sum([max(d, 0) for d in window]) / period
        loss = sum([max(-d, 0) for d in window]) / period
        rsi = 100 - (100 / (1 + (gain / loss))) if loss != 0 else 100
        res.append(rsi)
    return res

# Use the same data as before
data = [156797000.0, 154302000.0, 153300000.0, 151306000.0, 143623000.0, 144265000.0, 140320000.0, 137706000.0, 137750000.0, 136500000.0, 129896000.0, 128044000.0, 127333000.0, 131960000.0, 132574000.0, 130736000.0, 135366000.0, 136941000.0, 136334000.0, 136073000.0, 135744000.0, 129172000.0, 135626000.0, 138881000.0, 137390000.0, 133828000.0, 133598000.0, 135195000.0, 134986000.0, 137200000.0, 136700000.0, 134902000.0, 131795000.0, 129132000.0, 130682000.0, 128680000.0, 127135000.0, 131223000.0, 131469000.0, 131860000.0, 132200000.0, 130451000.0, 129236000.0, 128498000.0, 128152000.0, 127914000.0, 127161000.0, 128570000.0, 128067000.0, 128830000.0, 130150000.0, 131077000.0, 132386000.0, 136074000.0, 136299000.0, 132939000.0, 133174000.0, 133451000.0, 133503000.0, 133702000.0, 134602000.0, 139968000.0, 142160000.0, 140907000.0, 141083000.0, 140527000.0, 138940000.0, 137010000.0, 131849000.0, 132505000.0, 132864000.0, 131961000.0, 131644000.0, 128500000.0, 129474000.0, 129687000.0, 129079000.0, 124287000.0, 125210000.0, 117616000.0, 113416000.0, 116997000.0, 111882000.0, 107867000.0, 104990000.0, 102617000.0, 104587000.0, 103479000.0, 102136000.0, 99166000.0, 97328000.0, 100786000.0, 102850000.0, 102103000.0, 101944000.0, 100054000.0, 98622000.0, 98846000.0, 100065000.0, 100285000.0]

dates = ["Feb " + str(i+1) for i in range(21)] # Simplified for Feb only
wilder14 = calculate_rsi_wilder(data, 14)
wilder4 = calculate_rsi_wilder(data, 4)

print("Comparison for Feb:")
for i in range(len(data)-21, len(data)):
    idx = i
    d = "Feb " + str(21 - (len(data)-1-i))
    w14 = wilder14[idx]
    w4 = wilder4[idx]
    w14_v = f"{w14:.2f}" if w14 is not None else "None"
    w4_v = f"{w4:.2f}" if w4 is not None else "None"
    print(f"{d}: Price={data[idx]:,.0f}, RSI14={w14_v}, RSI4={w4_v}")
