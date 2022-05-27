def solve(**kwargs):
    n = kwargs['n']
    nums = kwargs['c']
    if n<=2:
        return max(nums)

    # do not steal house 0
    dp = [[0,0] for i in range(n)]
    for i in range(1,n):
        dp[i][1] = dp[i-1][0] + nums[i]
        dp[i][0] = max(dp[i-1][0], dp[i-1][1])
    ans1 = max(dp[-1])

    # steal house 0
    # do not steal house 1 & n-1
    dp = [[0,0] for i in range(n)]
    for i in range(2,n-1):
        dp[i][1] = dp[i-1][0] + nums[i]
        dp[i][0] = max(dp[i-1][0], dp[i-1][1])
    ans2 = max(dp[-2]) + nums[0]

    return max(ans1, ans2)