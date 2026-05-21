import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_cnc_proforma_data, read_port_data, read_vessel_class_data


def test_proforma_loader_records_vsa_metadata_without_hard_freezing():
	vesselpool = read_vessel_class_data()
	portpool, _ = read_port_data()
	proforma = read_cnc_proforma_data(portpool, vesselpool)
	lines = {line.name(): line for line in proforma['lines']}

	assert lines['CHN1CNC'].service_type == 'VSA'
	assert lines['CHN1CNC'].frozen is False
	assert lines['CHN1CNC'].week == 4.0
	assert lines['CHN1CNC'].frozen_weeks is None
	assert lines['CHN1CNC'].frozen_speed is None
	assert lines['CHN1CNC'].vessel_rank == 8
	assert lines['LCXP2CNC'].service_type == 'FIX'
	assert lines['LCXP2CNC'].frozen is False
