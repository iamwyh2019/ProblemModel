import random

n = int(input())
prices = [str(random.randint(1, 100)) for _ in range(n)]

print(n)
print(' '.join(prices))