import numpy as np
import typing
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Adam

from .port import PortPool

#查找不同 state 中有效的 action
class MatrixAnalyzer:
	def __init__(self, matrix: list[np.matrix]):
		"""
		Initialize the analyzer with a matrix T.
		Input:
			Out-degree adjoint matrix, k by N by N, where k denotes for the number of service lines
			and n denotes for the number of ports
			representing a service line
		"""
		self.T = np.array(matrix, dtype=np.float32)

	def find_valid_k(self, portpool: PortPool):
		"""
		对于输入的三维矩阵T,分析每个二维矩阵,找到满足条件的k值(按照每个service line循环)
		Input:
			self
		output:
			All actions
		"""
		n_layers = self.T.shape[0]
		valid_k_results={}

		for index in range(n_layers):
			T_layer = self.T[index]  # 获取当前层的二维矩阵
			n = T_layer.shape[0]     # 矩阵的维度

			## Part 1:
			## add point, 找到所有T_ij == 1的索引
			##
			valid_k_results_add = []
			indices = np.argwhere(T_layer == 1)

			# 检查每个找到的索引对(i, j)
			for (i, j) in indices:

				# 创建一个不包含当前i和j的索引数组
				valid_k_add = np.delete(np.arange(n), [i, j])

				# 检查这些k值是否同时满足T_ik == 0 和 T_kj == 0
				valid = (T_layer[i, valid_k_add] == 0) & (T_layer[valid_k_add, j] == 0)
				k_values_add = valid_k_add[np.where(valid)]

				for k in k_values_add:
					if T_layer[k, :].sum() + 1 <= portpool.get_port_by_idx(k).get_max_number_of_visit():
						valid_k_results_add.append([i, j, k])

				# 如果找到有效的k值，加入结果列表
				# if k_values_add.size > 0:
				#     valid_k_results_add.extend(k_values_add.tolist())

			## Part 2
			## delete point, 找到所有T_ij == 0的索引
			##
			valid_k_results_delete = []
			indices = np.argwhere(T_layer == 0)

			# 检查每个找到的索引对(i, j)
			for (i, j) in indices:
				# 创建一个不包含当前i和j的索引数组
				valid_k_delete = np.delete(np.arange(n), [i, j])

				# 检查这些k值是否同时满足T_ik == 1 和 T_kj == 1
				valid = (T_layer[i, valid_k_delete] == 1) & (T_layer[valid_k_delete, j] == 1)
				k_values_delete = valid_k_delete[np.where(valid)]

				for k in k_values_delete:
					valid_k_results_delete.append([i, j, k])

				# 如果找到有效的k值，加入结果列表
				# if k_values_delete.size > 0:
				#     valid_k_results_delete.extend(k_values_delete.tolist())

			#在每个service line中，合并add和delete的结果
			# valid_k_results = np.concatenate((valid_k_results_add, valid_k_results_delete), axis=0).T
			# valid_k_results[index] = valid_k_results
			valid_k_results[index] = {
				'add': valid_k_results_add,
				'delete': valid_k_results_delete
			}

		return valid_k_results

	def sample_actions(self, valid_k_results):
		sampled_actions = {}

		for index, actions in valid_k_results.items():
			all_possible_actions = []
			probabilities = []

			# Add valid actions with nonzero probability
			for action in actions['add']:
				all_possible_actions.append(('add', action))
				probabilities.append(1)  # Can set different probabilities if needed

			for action in actions['delete']:
				all_possible_actions.append(('delete', action))
				probabilities.append(1)  # Can set different probabilities if needed

			if probabilities:
				probabilities = np.array(probabilities)
				probabilities /= probabilities.sum()  # Normalize to form a probability distribution
				sampled_action = np.random.choice(len(all_possible_actions), p=probabilities)
				sampled_actions[index] = all_possible_actions[sampled_action]

		return sampled_actions

# Example Usage
# matrix = [[[0, 1, 0], [1, 0, 1], [0, 1, 0]], [[1, 0, 1], [0, 1, 0], [1, 0, 1]]]
# port_pool = PortPool()  # Assuming PortPool is properly defined elsewhere
# analyzer = MatrixAnalyzer(matrix)
# valid_k_results = analyzer.find_valid_k(port_pool)
# sampled_actions = analyzer.sample_actions(valid_k_results)
# print(sampled_actions)

#根据已找到的每个service line的有效k值，构造新的三维graph矩阵
class GraphMatrixGenerator:
	def __init__(self, matrix: list[list[list[float]]]):
		self.T = np.array(matrix, dtype=np.float32)

	def generate_new_graph_matrix(self, valid_k_dict: dict):
		"""
		根据已找到的每个service line的有效k值, 构造新的三维graph矩阵
		"""
		n_layers = self.T.shape[0]

		for index in range(n_layers):
			actions = valid_k_dict.get(index, {})
			add_actions =actions.get('add', [])
			delete_actions = actions.get('delete', [])

			# 对于'add'操作，设置T_ij = 0，T_ki = 1, T_jk = 1
			for (i, j, k) in add_actions:
				self.T[index, i, j] = 0
				self.T[index, k, i] = 1
				self.T[index, j, k] = 1

			# 对于'delete'操作，设置T_ij = 1，T_ki = 0, T_jk = 0
			for (i,j,k) in delete_actions:
				self.T[index, i, j] = 1
				self.T[index, k, i] = 0
				self.T[index, j, k] = 0

		return self.T

# matrix = [[[0, 1, 0], [1, 0, 1], [0, 1, 0]],
#           [[1, 0, 1], [0, 1, 0], [1, 0, 1]]]
# analyzer = GraphMatrixGenerator(matrix)

# valid_k_actions = {
#     0: {
#         'add': [(0, 2, 1)],
#         'delete': [(1, 2, 0)]
#     },
#     1: {
#         'add': [(1, 0, 2)],
#         'delete': [(2, 1, 0)]
#     }
# }

# new_matrix = analyzer.apply_valid_k_actions(valid_k_actions)
# print(new_matrix)


class GraphMatrices:
	def __init__(self, adj):
		self.adj = adj
		self.D_in = torch.diag(torch.sum(adj, dim=0))
		self.D_out = torch.diag(torch.sum(adj, dim=1))
		self.A_sym = (adj + adj.t() > 0).float()

	def get_normalized_adj(self):
		D_F_inv_sqrt = torch.diag(1.0 / torch.sqrt(torch.sum(self.adj, dim=1) + 1e-5))
		A_hat_F = torch.mm(torch.mm(D_F_inv_sqrt, self.adj), D_F_inv_sqrt)
		return A_hat_F

	def get_normalized_in_degree_adj(self):
		D_in_inv_sqrt = torch.diag(1.0 / torch.sqrt(torch.sum(self.A_sym, dim=0) + 1e-5))
		A_hat_in = torch.mm(torch.mm(D_in_inv_sqrt, self.A_sym), D_in_inv_sqrt)
		return A_hat_in

	def get_normalized_out_degree_adj(self):
		D_out_inv_sqrt = torch.diag(1.0 / torch.sqrt(torch.sum(self.A_sym, dim=1) + 1e-5))
		A_hat_out = torch.mm(torch.mm(D_out_inv_sqrt, self.A_sym.t()), D_out_inv_sqrt)
		return A_hat_out

# 定义DirectedGCN类，一个简单的神经网络模型，结合了不同类型的图特征并进行节点分类
class DirectedGCN(nn.Module):
	def __init__(self, num_features, num_classes):
		super(DirectedGCN, self).__init__()
		self.fc1 = nn.Linear(num_features * 3, num_classes)

	def forward(self, x, A_hat_F, A_hat_in, A_hat_out):
		Z_F = F.relu(torch.mm(A_hat_F, x))
		Z_in = F.relu(torch.mm(A_hat_in, x))
		Z_out = F.relu(torch.mm(A_hat_out, x))
		Z = torch.cat((Z_F, Z_in, Z_out), dim=1)
		y_hat = self.fc1(Z)
		return F.log_softmax(y_hat, dim=1)

# 环境类，用于提供与模型交互的环境和奖励机制
class Environment:
	def __init__(self, A, portpool):
		self.analyzer = MatrixAnalyzer(A)
		self.valid_k_dict = self.analyzer.find_valid_k(portpool)

	def get_reward(self, action):
		return len(self.valid_k_dict[action]) if action in self.valid_k_dict else -1

# 蒙特卡洛树搜索的简化实现
class MCTS:
	def __init__(self, env, model):
		self.env = env
		self.model = model
		self.memory = []

	def select_action(self, state):
		valid_actions = list(self.env.valid_k_dict.keys())
		return valid_actions[np.random.randint(len(valid_actions))]

	def run(self, state):
		action = self.select_action(state)
		reward = self.env.get_reward(action)
		self.memory.append((state, action, reward))

		x, A_hat_F, A_hat_in, A_hat_out = state
		y_hat = self.model(x, A_hat_F, A_hat_in, A_hat_out)
		loss = F.nll_loss(y_hat, torch.tensor([action[1]], dtype=torch.long))
		optimizer = Adam(self.model.parameters(), lr=0.01)
		optimizer.zero_grad()
		loss.backward()
		optimizer.step()

		return reward

def train(portpool, num_iterations=100):
	# 示例初始化
	A = np.array([
		[0, 1, 0, 0],
		[0, 0, 1, 0],
		[1, 0, 0, 1],
		[0, 0, 0, 0]
	], dtype=np.float32)
	num_features = 3
	num_classes = 2

	graph_matrices = GraphMatrices(torch.tensor(A))
	A_hat_F = graph_matrices.get_normalized_adj()
	A_hat_in = graph_matrices.get_normalized_in_degree_adj()
	A_hat_out = graph_matrices.get_normalized_out_degree_adj()

	env = Environment(A, portpool)
	model = DirectedGCN(num_features, num_classes)
	mcts = MCTS(env, model)

	rewards = []
	for _ in range(num_iterations):
		state = (torch.randn(4, num_features), A_hat_F, A_hat_in, A_hat_out)
		reward = mcts.run(state)
		rewards.append(reward)
		print("Iteration:", _, "Received Reward:", reward)

	return rewards

# Train the model
# rewards = train()
# print("Training completed. Rewards collected:", rewards)
