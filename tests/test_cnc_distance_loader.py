import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from cma.data_reader import (
	read_cnc_proforma_data,
	read_port_data,
	read_sailing_distance_data,
	read_vessel_class_data,
)
from cma.port import PortGraph


def test_cnc_distance_matrix_supplies_twkHH_to_vnc8q():
	portpool, _ = read_port_data()
	distances = read_sailing_distance_data(portpool)

	idx_twkHH = portpool.get_unique_index_by_id('TWKHH')
	idx_vnc8q = portpool.get_unique_index_by_id('VNC8Q')

	assert math.isclose(float(distances[idx_twkHH, idx_vnc8q]), 788.0)


def test_jtvscnc_route_distance_is_finite_with_cnc_matrix():
	vesselpool = read_vessel_class_data()
	portpool, _ = read_port_data()
	distances = read_sailing_distance_data(portpool)
	empty_demand = np.zeros(distances.shape)
	portgraph = PortGraph(portpool, distances, empty_demand, filter_by_demand=False)
	proforma = read_cnc_proforma_data(portpool, vesselpool)

	jtvs = next(line for line in proforma['lines'] if line.name() == 'JTVSCNC')

	assert math.isfinite(float(jtvs.get_distance(portgraph)))
