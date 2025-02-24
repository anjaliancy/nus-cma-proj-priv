"""
Module `nn.py`

Simpliest Neural Network
"""

from torch import nn


class SimpleNN(nn.Module):
	"""class SimpleNN
	Simple Neural Network

	Input:
		1. service lines (S_t)
		2. weekly demand rate (D_t)

	Output:
		1. Probabilities of each action

	"""
	def __init__(self):
		super().__init__()
		self.fc = nn.Linear(10, 1)

	def forward(self, x):
		x = self.fc(x)
		return x


model = SimpleNN()
print(model)
