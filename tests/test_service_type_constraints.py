import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_cnc_proforma_data, read_port_data, read_vessel_class_data


def test_proforma_loader_records_vsa_metadata():
	vesselpool = read_vessel_class_data()
	portpool, _ = read_port_data()
	proforma = read_cnc_proforma_data(portpool, vesselpool)
	lines = {line.name(): line for line in proforma['lines']}

	assert lines['CHN1CNC'].service_type == 'VSA'
	assert lines['CHN1CNC'].week == 4.0
	assert lines['CHN1CNC'].frozen_speed is None
	assert lines['CHN1CNC'].vessel_rank == 8


def test_proforma_loader_freezes_topology_for_vsa_and_fix_but_not_rank_weeks():
	vesselpool = read_vessel_class_data()
	portpool, _ = read_port_data()
	proforma = read_cnc_proforma_data(portpool, vesselpool)
	lines = {line.name(): line for line in proforma['lines']}

	# VSA: topology AND rank/weeks locked - partner-run, CMA can't touch any of it
	vsa_line = lines['CHN1CNC']
	assert vsa_line.service_type == 'VSA'
	assert vsa_line.frozen is True
	assert vsa_line.frozen_rank_weeks is True

	# FIX: topology (port rotation) locked, but rank/weeks stay optimisable
	fix_line = lines['LCXP2CNC']
	assert fix_line.service_type == 'FIX'
	assert fix_line.frozen is True
	assert fix_line.frozen_rank_weeks is False

	# OWN: nothing locked
	own_lines = [ln for ln in lines.values() if ln.service_type == 'OWN']
	assert own_lines, 'expected at least one OWN line in proforma data'
	for own_line in own_lines:
		assert own_line.frozen is False
		assert own_line.frozen_rank_weeks is False
