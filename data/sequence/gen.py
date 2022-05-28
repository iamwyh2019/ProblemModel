import random

n = int(input())
arr = [str(random.randint(-500, 500)) for _ in range(n)]

print(n)
print(' '.join(arr))
print(int(n/2))