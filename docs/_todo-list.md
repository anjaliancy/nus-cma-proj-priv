# CAM project To Do List



## 1. Tasks

- [ ] Layer 0. Given lines, calculate minimized cost. Focusing on cargo allocation problem and everything are on average.

    - [x] Basic framework.

    - [x] Only consider average demand rate per week.
    - [x] Only consider line level capacity, not the vessels.
    - [x] Considering number of vessesl as integer variables into MIP.
    - [ ] Consider more realistic type of demands.
    - [ ] Estimate average port call cost and transshipment cost per week.
    - [x] Estimate average bunkering cost per week
    - [x] Estimate average chartering cost per week

- [ ] Layer 1 MCTS propotype

    - [x] Basic framework
    - [x] Expand the tree slower (**Linsheng**)
    - [x] Consider probablities distribution of actions in expansition (PUCT) (**Linsheng**)
    - [ ] Build policty network to be embedded (**Xuefei**)

    - [ ] Better UCB settings to balance exploration and exploitation
    - [ ] Better visualization

- [ ] Layer 1 MCTS with neural network

    - [ ] A basic framework
    - [ ] Using GNN to learn graph information, methedology (**Xuefei**)
    - [ ] Large network

- [ ] Layer 2 finer version

    - [ ] Consider more realistic type of demands in cargo allocation problem

    - [ ] Scheduling of ships given lines and more realistic demands



## 2. Problems

Currently, we are building the basic framework of layer 1 (MCTS with neural network). Below are the problems that we have to solve:

- [ ] The representation of directed network as neural network input.
- [ ] How to extract network information? By GNN?
- [ ]

