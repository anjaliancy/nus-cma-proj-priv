from typing import Optional

def cloest_pair(a: list[int], b: list[int]) -> tuple[Optional[tuple[int,int]], float]:
	"""Pick the closest pair from two lists `a` and `b`
	"""
	a.sort()
	b.sort()

	i, j = 0, 0
	min_diff = float('inf')
	cloest_pair = None

	while i < len(a) and j < len(b):
		diff = abs(a[i] - b[j])

		if diff < min_diff:
			min_diff = diff
			cloest_pair = (a[i], b[j])

		if a[i] < b[j]:
			i += 1
		else:
			j += 1
	return cloest_pair, min_diff
