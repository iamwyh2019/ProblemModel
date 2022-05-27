def solve(**kwargs):
    n = kwargs['n']
    prices = kwargs['p']

    dp = [[0,0,0,0,0] for i in range(n)]
    dp[0][1] = dp[0][3] = -prices[0]
    for i in range(1, n):
        dp[i][0] = dp[i-1][0]
        dp[i][1] = max(dp[i-1][1], dp[i-1][0]-prices[i])
        dp[i][2] = max(dp[i-1][2], dp[i-1][1]+prices[i])
        dp[i][3] = max(dp[i-1][3], dp[i-1][2]-prices[i])
        dp[i][4] = max(dp[i-1][4], dp[i-1][3]+prices[i])
    
    return max(dp[-1])