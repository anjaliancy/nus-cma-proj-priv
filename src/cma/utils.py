import base64
import io

import numpy as np
import pandas as pd
import statsmodels.api as sm

from matplotlib import pyplot as plt
from IPython.display import display, HTML
from statsmodels.regression.linear_model import RegressionResultsWrapper

from .vessel import VesselPool
from .port import PortGraph
from .serviceline import ServiceLine
from .data_reader import \
	read_vessel_class_data, \
	read_port_data, \
	read_demand_data, \
	read_sailing_distance_data, \
	read_current_line_data


# region Visualizaton
#
def display_two_figs(fig1, fig2):
	"""
	display two figures in IPython
	"""
	def _fig_to_base64(fig):
		buf = io.BytesIO()
		fig.savefig(buf, format="png", bbox_inches="tight")
		buf.seek(0)
		plt.close(fig)
		return base64.b64encode(buf.getvalue()).decode()
	img1 = _fig_to_base64(fig1)
	img2 = _fig_to_base64(fig2)
	display(HTML(f"""
		<div style="display: flex; justify-content: center;">
		<img src="data:image/png;base64,{img1}" width="45%" style="margin-right: 10px;">
		<img src="data:image/png;base64,{img2}" width="45%">
		</div>
	"""))
#
# endregion

# region - Predict Weeks
#
def _extract_line(line: ServiceLine, portgraph: PortGraph, vesselpool: VesselPool):
	"""
	Make sure that `line` is not empty
	"""
	inflows, outflows = portgraph.get_demand_flows()
	current_lines_sailing_distance = line.get_distance(portgraph)
	current_lines_stops_number = line.number_of_port()
	sum_prods = 0
	sum_inflows = 0
	sum_outflows = 0
	for p in line.tolist_port():
			sum_inflows += inflows[portgraph.get_unique_index(p)]
			sum_outflows += outflows[portgraph.get_unique_index(p)]
			sum_prods += sum(p.get_producticity(vesselpool))
	current_lines_ave_productivity = sum_prods / line.number_of_port()
	current_lines_ave_demandinflow = sum_inflows / line.number_of_port()
	current_lines_ave_demandoutflow = sum_outflows / line.number_of_port()
	return {
		'const': 1.0,
		'weeks': line.week,
		'sailing_distance': current_lines_sailing_distance,
		'stops_number': current_lines_stops_number,
		'ave_productivity': current_lines_ave_productivity,
		'ave_demand_inflows': current_lines_ave_demandinflow,
		'ave_demand_outflows': current_lines_ave_demandoutflow
	}

def _extract_lines(lines: list[ServiceLine], portgraph: PortGraph, vesselpool: VesselPool) -> pd.DataFrame:
	"""
	Make sure that each line in `lines` is not empty
	"""
	df = pd.DataFrame()
	for line in lines:
		rec = _extract_line(line, portgraph, vesselpool)
		df_new = pd.DataFrame([rec])
		df = pd.concat([df, df_new], ignore_index=True)
	return df

def update_week_predictor(df: pd.DataFrame, lines: list[ServiceLine],
		portgraph: PortGraph, vesselpool: VesselPool,
	) -> tuple[RegressionResultsWrapper, pd.DataFrame]:
	# update old `df`
	new_row = _extract_lines(lines, portgraph, vesselpool)
	df = pd.concat([df, new_row], ignore_index=True)
	# run OLS
	xs = df.drop(columns=['weeks'])
	y = df['weeks']
	model = sm.OLS(y, xs).fit()
	return model, df

def apply_prediction(model: RegressionResultsWrapper,
		lines: list[ServiceLine], portgraph: PortGraph, vesselpool: VesselPool,
	) -> np.ndarray:
	predicts = []
	for line in lines:
		if line.number_of_port() == 0:
			predicts.append(0.0)
			continue
		df = _extract_lines([line], portgraph, vesselpool)
		xs = df.drop(columns=['weeks'])
		predict = model.predict(xs)[0]
		if predict < 3/4:
			predict = 1/2
		elif predict > 9:
			predict = 9
		else:
			predict = round(predict)
		predicts.append(predict)
	return np.array(predicts)

def create_week_predictor():
	vesselpool = read_vessel_class_data()
	portpool, _ = read_port_data()
	_, weekly_demand = read_demand_data(portpool)
	dist_mat = read_sailing_distance_data(portpool)
	portgraph = PortGraph(portpool, dist_mat, weekly_demand, None)
	current_lines, _ = read_current_line_data(portpool, warn=False)
	model, _ = update_week_predictor(pd.DataFrame(), current_lines, portgraph, vesselpool)
	return model

#
# endregion
