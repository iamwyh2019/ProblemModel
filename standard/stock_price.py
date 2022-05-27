def solve(**kwargs):
    n = kwargs['n']
    prices = kwargs['p']
    
    dp = [[0,0,0] for i in range(n)]
    dp[0][1] = -prices[0]

    for i in range(1,n):
        dp[i][0] = max(dp[i-1][0], dp[i-1][2])
        dp[i][1] = max(dp[i-1][1], dp[i-1][0]-prices[i])
        dp[i][2] = dp[i-1][1]+prices[i]
    
    return max(dp[-1])