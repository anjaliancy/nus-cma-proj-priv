"""
Module `mcts`

Implementation of Monte Carlo Tree Search (MCTS) algorithm for CAM project
"""

# from __future__ import annotations  # For Python < 3.11
from typing import Optional  # For Python 3.11+
import math
import random
import pickle

from .vessel import VesselPool
from .port import PortGraph
from .servicegraph import ServiceGraph, GraphAction


class MonteCarloTreeSearchNode:
	"""class MonteCarloTreeSearchNode
	"""
	# each node contain a graph of services
	graph: ServiceGraph

	# ucb related
	number_of_visits: int
	sum_value: float
	prior_prob: float

	# tree structure
	borns: list[GraphAction]
	children: list['MonteCarloTreeSearchNode']
	parent: Optional['MonteCarloTreeSearchNode']

	def __init__(self, service_graph: ServiceGraph, prior_prob: float, parent: Optional['MonteCarloTreeSearchNode'] = None):
		"""
		`prior_prob` is taken from NN
		"""
		# 1. graph
		self.graph = service_graph

		# 2. UCB related
		self.number_of_visits = 0
		self.sum_value = 0
		self.prior_prob = prior_prob

		# 3. tree structure
		self.borns = []
		self.children = []
		self.parent = parent

	# def get_all_actions(self, portgraph: PortGraph) -> list[GraphAction]:
	# 	"""
	# 	Return a list of graph actions, where graph action is a list of actions
	# 	"""
	# 	if self.graph is None:
	# 		return None
	# 	port_space = []
	# 	for service in self.graph.tolist_serviceLine():
	# 		port_space.append(service.get_all_valid_actions(portgraph))
	# 	return list(itertools.product(*port_space))

	def get_all_actions_and_probs(self, portgraph: PortGraph) -> tuple[list[GraphAction], list[float]]:
		_, actions = self.graph.get_feasible_actions(portgraph)
		probs = [random.uniform(0, 1) for _ in actions]
		## TO DO
		# Using Neural Network
		return actions, probs

###############################################################################
# Tree structure related
###############################################################################

	def get_depth(self) -> int:
		"""How many upsprings
		"""
		depth = 0
		the_node = self
		while the_node.parent is not None:
			the_node = the_node.parent
			depth += 1
		return depth

	def total_number_of_sub_nodes(self) -> int:
		# num = 1
		# the_node = self
		# for child in the_node.children:
		# 	num += child.total_number_of_sub_nodes()
		# return num
		return 1 + sum(child.total_number_of_sub_nodes() for child in self.children)

	def best_sub_node(self, portgraph: PortGraph) -> 'MonteCarloTreeSearchNode':
		the_node = self
		the_node_reward = the_node.current_state_reward()
		for child in the_node.children:
			if child.number_of_visits == 0:
				continue
			best_c_offspring: 'MonteCarloTreeSearchNode' = child.best_sub_node(portgraph)
			if best_c_offspring.current_state_reward() > the_node_reward:
				the_node = best_c_offspring
				the_node_reward = the_node.current_state_reward()
		return the_node

	def best_sub_node_byucb(self, portgraph: PortGraph, c_param: float) -> 'MonteCarloTreeSearchNode':
		the_node = self
		the_node_ucb_v = the_node.pucb(c_param)
		for child in the_node.children:
			if child.number_of_visits == 0:
				continue
			best_c_offspring: 'MonteCarloTreeSearchNode' = child.best_sub_node_byucb(portgraph, c_param)
			if best_c_offspring.pucb(c_param) > the_node_ucb_v:
				the_node = best_c_offspring
				the_node_ucb_v = the_node.pucb(c_param)
		return the_node

	# def is_fully_expand(self, portgraph: PortGraph, max_depth: int) -> bool:
	# 	all_actions = self.get_all_actions(portgraph)
	# 	depth = self.get_depth()
	# 	if depth < max_depth and len(self.children) < len(all_actions):
	# 		return False
	# 	for c in self.children:
	# 		if c.is_fully_expand(portgraph, max_depth) is False:
	# 			return False
	# 	return True

	def add_child(self, graph_action: GraphAction,
			portgraph: PortGraph, prior_prob: float, max_depth: int) -> Optional['MonteCarloTreeSearchNode']:
		"""
		Input:
			`graph_action`
		Work:
			- Create a child node by the given `graph_action`
			- Append the created node to `self.children`
			- Append the used action to `self.borns`
		Return:
			- Return the created node if successful
			- Return None if the maximum depth is reached
		"""
		if self.get_depth() >= max_depth:
			return None
		# if exists already: return the child node
		if graph_action in self.borns:
			return self.children[self.borns.index(graph_action)]
		# for c in self.children:
		# 	c_exist: bool = True
		# 	for (service_action, parent_service_action) in zip(graph_action, c.graph_action):
		# 		if not service_action.is_same(parent_service_action):
		# 			c_exist = False
		# 			break
		# 	if c_exist:
		# 		return c
		new_graph = self.graph.update_by_graph_action(graph_action, portgraph)
		child_node = MonteCarloTreeSearchNode(new_graph, prior_prob, self)
		self.children.append(child_node)
		self.borns.append(graph_action)
		return child_node

###############################################################################
# MCTS related
###############################################################################

	def rollout(self, portgraph: PortGraph, vesselpool: VesselPool, discount_fac: float, valid_weight_proportion: float):
		"""
		Input:
			`discount_fac`
			`valid_weight_proportion`
		Work:
			1. Simulate paths of adjustments randomly
			2. Evaluate the value of `self` after several steps of adjustments
		"""
		# solve immediate value
		self.graph.solve_approximated_cost(portgraph, vesselpool)

		# create a temporary root node whose parent is None
		tmp_root = MonteCarloTreeSearchNode(self.graph, self.prior_prob, None)
		the_node = tmp_root

		total_weight = 1 / (1 - discount_fac)
		sum_weight = 1.0

		while sum_weight < total_weight * valid_weight_proportion:
			# Create a random `graph_action`
			all_actions, all_probs = the_node.get_all_actions_and_probs(portgraph)
			n_acts = len(all_actions)
			if n_acts == 0:
				print("Warning: no valid action in rollout.")
				return
			rand_idx = random.choices(list(range(n_acts)), all_probs)[0]
			the_action = all_actions[rand_idx]
			the_prior = all_probs[rand_idx]
			# Add `child_node` to `the_node`
			child_node = the_node.add_child(the_action, portgraph, the_prior, 999999)
			assert child_node is not None
			# child_node is not None since `max_depth = infty`

			the_node = child_node
			the_node.graph.solve_approximated_cost(portgraph, vesselpool)
			# Check stopping
			sum_weight *= discount_fac
			sum_weight += 1

		sum_weight = 1.0
		value = the_node.current_state_reward()
		while sum_weight < total_weight * valid_weight_proportion and isinstance(the_node.parent, MonteCarloTreeSearchNode):
			the_node = the_node.parent
			# the_node is not None since `valid_weight_proportion` < 1
			value *= discount_fac
			value += the_node.current_state_reward()
			sum_weight *= discount_fac
			sum_weight += 1
		value *= total_weight / sum_weight
		self.sum_value += value
		self.number_of_visits += 1

	def back_propagate(self, discount_fac: float):
		"""
		Input:
			`discount_fac`
		Work:
			1. Update the sum value and number of visits of all upper nodes
			2. Update neural network
		"""
		the_node = self
		while the_node.parent is not None:
			value = the_node.sum_value / the_node.number_of_visits
			the_node.parent.sum_value += the_node.parent.current_state_reward()
			the_node.parent.sum_value += value * discount_fac
			the_node.parent.number_of_visits += 1
			the_node = the_node.parent
		## TO DO
		# update NN
		# use NN to update prob of each node

	def expand(self, portgraph: PortGraph, vesselpool: VesselPool,
			max_depth: int, c_param: float, discount_fac: float, valid_weight_proportion: float):
		"""A more balanced way of expansion
		"""
		if self.get_depth() == max_depth:
			print("到底了，多进行一次rollout！")
			self.rollout(portgraph, vesselpool, discount_fac, valid_weight_proportion)
			self.back_propagate(discount_fac)
			return

		actions, probs = self.get_all_actions_and_probs(portgraph)
		pucb_list = []

		for idx, action in enumerate(actions):
			if action not in self.borns:
				pucb = c_param * probs[idx] * self.number_of_visits**0.5
			else: # in borns/children
				c = self.children[self.borns.index(action)]
				pucb = c.pucb(c_param)
			pucb_list.append(pucb)

		selected_act_idx = pucb_list.index(max(pucb_list))
		selected_act = actions[selected_act_idx]

		if selected_act not in self.borns:
			self.add_child(selected_act, portgraph, probs[selected_act_idx], max_depth)
		else:
			print('在 expand 的时候找到已出生的孩子节点，递归进行 expand！')
			c = self.children[self.borns.index(selected_act)]
			c.expand(portgraph, vesselpool, max_depth, c_param, discount_fac, valid_weight_proportion)

	def select(self, c_param: float) -> 'MonteCarloTreeSearchNode':
		"""
		Return:
			1. the selected leaf node
			2. PUCB of that node
		"""
		if len(self.children) == 0:
			return self
		weights = [c.pucb(c_param) for c in self.children]
		c = self.children[weights.index(max(weights))]
		return c.select(c_param) if c.pucb(c_param) > self.pucb(c_param) else self
		# if c.pucb(c_param) > self.pucb(c_param):
		# 	return c.select(c_param)
		# else:
		# 	return self

	def search_step(self, portgraph: PortGraph, vesselpool: VesselPool, max_depth: int,
		 	discount_fac: float, valid_weight_proportion: float, c_param: float = 1):
		"""Using the more balanced way of expansion
		"""
		c = self.select(c_param)

		if c.number_of_visits == 0:
			c.rollout(portgraph, vesselpool, discount_fac, valid_weight_proportion)
			c.back_propagate(discount_fac)
			print("call rollout")
		else:
			c.expand(portgraph, vesselpool, max_depth, c_param, discount_fac, valid_weight_proportion)
			print("call expand")


###############################################################################
# UCB related
###############################################################################

	def ucb(self, c_param: float = 1.0) -> float:
		if self.number_of_visits == 0:
			return float('inf')
		ret = self.sum_value / self.number_of_visits
		if self.parent is None:
			return ret
		tmp = math.sqrt(2 * math.log(self.parent.number_of_visits) / self.number_of_visits)
		return ret + c_param * tmp

	def pucb(self, c_param: float) -> float:
		if self.number_of_visits == 0:  # newly expanded, but not rollout yet
			q_value = 0.0
		else:
			q_value = self.sum_value / self.number_of_visits
		if self.parent is None:
			tmp = math.sqrt(self.number_of_visits) / (1 + self.number_of_visits)
		else:
			tmp = math.sqrt(self.parent.number_of_visits) / (1 + self.number_of_visits)
		return q_value + c_param * self.prior_prob * tmp

	def current_state_reward(self) -> float:
		return 1.0e4 / self.graph.total_cost()



class MonteCarloTree:
	"""class MonteCarloTree
	"""
	root_node: MonteCarloTreeSearchNode
	portgraph: PortGraph
	vesselpool: VesselPool

	discount_fac: float  # discount factor `beta`
	c_param: float
	max_depth: int

	def __init__(self, service_graph: ServiceGraph,
			portgraph: PortGraph,
			vesselpool: VesselPool,
			discount_fac:float=0.5,
			max_depth: int=5,
			c_param:float=0.0005):
		'''
		Input:
			`max_depth`: depth of root is zero
		'''
		self.root_node = MonteCarloTreeSearchNode(service_graph, 1, None)
		self.portgraph = portgraph
		self.vesselpool = vesselpool

		self.discount_fac = discount_fac
		self.c_param = c_param
		self.max_depth = max_depth

	def run(self, epochs: int):
		for _ in range(epochs):
			self.root_node.search_step(
				self.portgraph,
				self.vesselpool,
				self.max_depth,
				self.discount_fac,
				valid_weight_proportion=0.9
			)

###############################################################################
# Statistics
###############################################################################

	def total_number_of_nodes(self):
		return self.root_node.total_number_of_sub_nodes()

	def best_node(self) -> MonteCarloTreeSearchNode:
		return self.root_node.best_sub_node(self.portgraph)

	def best_node_byucb(self) -> MonteCarloTreeSearchNode:
		return self.root_node.best_sub_node_byucb(self.portgraph, self.c_param)

	# def is_fully_expand(self):
	# 	return self.root_node.is_fully_expand(self.portgraph, self.max_depth)

###############################################################################
# Utils
###############################################################################

	def save_tree(self, file: Optional[str] = None) -> None:
		if file is not None:
			with open(file, 'wb') as f:
				pickle.dump(self, f)

	@staticmethod
	def load_tree(file: Optional[str] = None) -> Optional['MonteCarloTree']:
		if file is not None:
			with open(file, 'rb') as f:
				return pickle.load(f)
		return None
