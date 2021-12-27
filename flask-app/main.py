from flask import Flask, render_template, url_for, redirect, request, Response
import pandas as pd
import plotly
import datetime
import plotly.express as px
from urllib.request import urlopen
import json
import geojson
import math
import pickle
import fbprophet
import plotly.graph_objs as go
from scipy.stats import boxcox
from scipy.special import inv_boxcox
import requests
import time
import io
import csv
import pymysql
from app import app
from db import mysql

colors = [
    "#151515", "#2A2A29", "#3F3F3E","#545453","#696968","#7E7E7C","#939391","#A8A8A6", 
    "#888888", "#909090", "#999998","#A1A1A0","#A9A9A8","#B1B1AF","#B9B9B7","#C2C2BF","#DBDBD9", 
    "#E0E0DD", "#E4E4E2", "#E9E9E7"
    ]

ccaa_names = {
        'AN': 'Andalucia',
        'AR': 'Aragon',
        'AS': 'Asturias',
        'CB': 'Cantabria',
        'CE': 'Ceuta',
        'CL': 'Castilla-Leon',
        'CM': 'Castilla-La Mancha',
        'CN': 'Canarias',
        'CT': 'Cataluña',
        'EX': 'Extremadura',
        'GA': 'Galicia',
        'IB': 'Baleares',
        'MC': 'Murcia',
        'MD': 'Madrid',
        'ML': 'Melilla',
        'NC': 'Navarra',
        'PV': 'Pais Vasco',
        'RI': 'La Rioja',
        'VC': 'Valencia'
}

def millify(n):
    n = float(n)
    millnames = ['',' Thousand',' Million',' Billion',' Trillion']
    millidx = max(0,min(len(millnames)-1, int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

    return '{:.0f}{}'.format(n / 10**(3 * millidx), millnames[millidx])
    
def get_dataframe(table_name):
	conn = None
	cursor = None
	try:
		conn = mysql.connect()
		cursor = conn.cursor(pymysql.cursors.DictCursor)

		cursor.execute("SELECT * FROM {}".format(table_name))
		result = cursor.fetchall()
		dataframe = pd.DataFrame(result)
		return dataframe
	except Exception as e:
		return False
	finally:
		cursor.close() 
		conn.close()

def download_data(table, column_names) : 
	conn = None
	cursor = None
	try:
		conn = mysql.connect()
		cursor = conn.cursor(pymysql.cursors.DictCursor)
		query = "SELECT {cols} FROM {table_name}".format(cols = ",".join(column_names), table_name = table)
		cursor.execute(query)
		result = cursor.fetchall()
		header = list(result[0].keys())
		output = io.StringIO()
		writer = csv.DictWriter(output, fieldnames = header)
		writer.writeheader()
		for row in result:
			writer.writerow(row)
		output.seek(0)
		filename = "cases_data" if table=="covid_cases" else "vaccines_data"
		return Response(
            output, 
            mimetype="text/csv", 
            headers={"Content-Disposition":"attachment;filename={}.csv".format(filename)}
        )
	except Exception as e:
		print(e)
	finally:
		cursor.close() 
		conn.close()

def apply_legend_colors(figure):
    for i in range(len(figure['data'])) : 
        print(figure['data'][i]["legendgroup"])
        figure['data'][i]['line']['color']=colors[(i*3)]
    return figure

def generate_labels(keys, values) : 
    labels = {keys[0]: "<b>{}</b>".format(values[0])}
    labels.update({keys[i]: "<i>{}</i>".format(values[i]) for i in range(1, len(values))})
    return labels

def generate_colors(keys):
    colors_gen = dict(zip(keys, colors[:len(keys)]))
    return colors_gen

def generate_figureJSON(figure):
    return json.dumps(figure, cls=plotly.utils.PlotlyJSONEncoder)

def custom_legend_name(figure, new_names, c):
    for i in range(len(new_names)):
        figure.data[i].name = new_names[i]
        figure.data[i].line.color = c[i]
    return figure

def choropleth_map(data) : 

    full_dataframe = data[["Date", "nb_cases", "ccaa_iso"]]
    full_dataframe["ccaa_name"] = full_dataframe["ccaa_iso"].apply(lambda x : ccaa_names[x])
    #select the last date in dataframe
    full_dataframe["Date"].values[-1]
    _14_days_b = full_dataframe["Date"].to_list()[-1]-datetime.timedelta(days = 14)
    full_dataframe = full_dataframe.set_index('Date')
    full_dataframe = full_dataframe.loc[_14_days_b.strftime("%Y-%m-%d"):].groupby("ccaa_name", as_index = False).sum()

    with open("spain-communities.geojson", "r") as geojson_file:
        states = geojson.load(geojson_file)

    #creating states
    states_dict = {}
    for feature in states["features"]:
        feature["id"] = feature["properties"]["cod_ccaa"]
        states_dict[feature["properties"]["name"]] = feature["id"]
    print("\n".join("Autonomous communities name = '{}' corresponding Id = '{}'".format(key, value) for key, value in states_dict.items()))
    
    full_dataframe["id"] = full_dataframe["ccaa_name"].apply(lambda x: states_dict[x])
    fig = px.choropleth(
        data_frame = full_dataframe,
        locations = "id",
        geojson=states,
        color="nb_cases",
        hover_name = "ccaa_name",
        color_continuous_scale="gray_r", 
        labels={
        "nb_cases": "<b>Total Covid-19 cases:</b>"
        }
    )
    fig.update_geos(
        fitbounds="locations", 
        visible=False
    )
    fig.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )

    return fig

def standard_plotG(data, y_column, color_column, labels_keys, labels_values, title):
    data = data.set_index('Date')
    data["ccaa_name"] = data["ccaa_iso"].apply(lambda x : ccaa_names[x])
    #getting colors
    grey_scale = generate_colors(data[color_column])
    fig = px.line(
        data, 
        x=data.index, 
        y=y_column, 
        color=color_column,
        color_discrete_sequence=px.colors.qualitative.Alphabet,
        color_discrete_map=grey_scale,
        template="simple_white",
        title = "<b>{}</b>".format(title), 
        labels = generate_labels(labels_keys, labels_values)
    )
    fig.update_traces(textposition="bottom right")
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label = "ALL")
            ])
        )
    )
    fig.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )

    return fig

def standard_plot(data, y_column, labels_keys, labels_values):
    data = data.set_index('Date')
    data["ccaa_name"] = data["ccaa_iso"].apply(lambda x : ccaa_names[x])
    grouped_data = data.groupby(data.index).sum()
    fig = px.line(
        grouped_data, 
        x=grouped_data.index, 
        y=y_column, 
        template="simple_white",
        labels=generate_labels(labels_keys, labels_values)
        )
    fig.update_traces(textposition="bottom right")
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label = "ALL")
            ])
        )
    )
    fig.update_traces(line_color='#151515')
    fig.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )

    return fig

def bar_plot(data, x_column, y_column, text_column, labels_keys, labels_values, title):
    data = data.set_index('Date')
    data["ccaa_name"] = data["ccaa_iso"].apply(lambda x : ccaa_names[x])
    #getting colors
    grey_scale = generate_colors(data["ccaa_name"])
    fig = px.bar(
        data.groupby("ccaa_name", as_index = False).sum(), 
        y=y_column, 
        x=x_column, 
        text=text_column,
        template="simple_white", 
        title = "<b>{}</b>".format(title), 
        color='ccaa_name',
        labels=generate_labels(labels_keys, labels_values), 
        color_discrete_map=grey_scale
        )
    fig.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
    fig.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )

    return fig

def cases_main(data, y_column, labels_keys, labels_values):
    data = data.set_index('Date')
    grouped_cases = data.groupby(data.index).sum()
    gov_df =  pd.read_csv("gov_m.csv")
    gov_df = gov_df.set_index("Date")
    
    fig = px.line(
        grouped_cases, 
        x=grouped_cases.index, 
        y="nb_cases", 
        template="simple_white",
        labels=generate_labels(labels_keys, labels_values)
        )
    for date_g in gov_df.to_dict()["mesure"] : 
        fig.add_vline(
            x=datetime.datetime.strptime(date_g, "%Y-%m-%d").timestamp()*1000, 
            line_width=2, 
            line_dash="dash", 
            line_color="#151515", 
            annotation_text = gov_df.to_dict()["mesure"][date_g]
        )
    fig.update_layout(annotations=[{**a, **{"y":.5,"yanchor":"bottom","textangle":-90}}  for a in fig.to_dict()["layout"]["annotations"]])
    fig.update_traces(textposition="bottom right")
    fig.update_xaxes(
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1M", step="month", stepmode="backward"),
                dict(count=6, label="6M", step="month", stepmode="backward"),
                dict(count=1, label="YTD", step="year", stepmode="todate"),
                dict(count=1, label="1Y", step="year", stepmode="backward"),
                dict(step="all", label = "ALL")
            ])
        )
    )
    fig.update_traces(line_color='#151515')
    fig.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )

    return fig

def forecasting(data) : 
    #creating data structure 
    ret_dict = {}
    #import original data
    data = data.groupby("Date", as_index = False).sum()[["Date", "nb_cases"]].iloc[55:]

    data["Date"] = pd.to_datetime(data["Date"])
    data.columns = ['ds', 'y']
    last_date = data.iloc[-1]["ds"]

    #load model 
    with open('models/prophet_v2.pckl', 'rb') as fin:
        model = pickle.load(fin)

    #making forecast cox_box factor please see the fbprophet notebook ::::::::
    future = model.make_future_dataframe(periods=14)
    forecast = model.predict(future)
    forecast[['yhat','yhat_upper','yhat_lower']] = forecast[['yhat','yhat_upper','yhat_lower']].apply(lambda x: inv_boxcox(x, 0.26807530199503693))

    #forecast
    day_after = forecast.loc[forecast["ds"] == (last_date+datetime.timedelta(days=1)).strftime("%Y-%m-%d")]
    data_info = day_after[['yhat','yhat_upper','yhat_lower']].to_numpy()[0].astype(int)

    #building the visualization
    trace1 = go.Scatter(
        name = 'Forecast',
        mode = 'lines',
        x = list(forecast['ds']),
        y = list(forecast['yhat']),
        marker=dict(
            color='#d472bc'
        )
    )
    upper_band = go.Scatter(
        name = 'Upper band',
        mode = 'lines',
        x = list(forecast['ds']),
        y = list(forecast['yhat_upper']),
        line= dict(color='#add8e6'),
        fill = 'tonexty'
    )
    lower_band = go.Scatter(
        name= 'Lower band',
        mode = 'lines',
        x = list(forecast['ds']),
        y = list(forecast['yhat_lower']),
        line= dict(color='#add8e6')
    )
    tracex = go.Scatter(
        name = 'The actual cases',
        mode = 'markers',
        x = list(data['ds']),
        y = list(data['y']),
        marker=dict(
            color='LightSkyBlue',
            size=5,
            opacity=0.5,
            line=dict(
                color='#000000',
                width=1
            )
        )
    )
    layout = dict(
        title='New COVID-19 in Spain Prediction Using FbProphet',
        xaxis=dict(title = 'Dates', ticklen=2, zeroline=True), 
        template = "simple_white", 
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    combine=dict(
        data=[lower_band, upper_band, trace1, tracex],
        layout=layout
    )

    ret_dict["figure"] = combine
    ret_dict["info"] = data_info
    ret_dict["last_update"] = last_date

    return ret_dict

#prepare data
cases_dataframe = get_dataframe('covid_cases')
vaccines = get_dataframe('vaccins')
cases_dataframe["Date"] = pd.to_datetime(cases_dataframe["Date"])
vaccines["Date"] = pd.to_datetime(vaccines["Date"])

#creating app route
@app.route('/')
def index():
    #creating vaccines figure1
    vaccines_figure1 = standard_plot(
        vaccines,
        ["No. People vaccinated", "Doses administered", "Total doses delivered"], 
        ["x", "variable", "value"], 
        ["Date", "Available indicators", "Vaccines"]
    )
    #applying colors change 
    vaccines_figure1 = apply_legend_colors(vaccines_figure1)

    vaccines_figure2 = standard_plotG(
        vaccines,
        ["No. People vaccinated"], 
        "community",
        ["No. People vaccinated", "index", "community"], 
        ["Vaccines", "Date", "Autonomous communities"], 
        "Vaccines by Autonomous communities"
    )

    cases_figure1 = cases_main(
        cases_dataframe, 
       "nb_cases", 
       ["nb_cases","Date"], 
       ["New cases","Date"]
    )

    cases_figure2 = standard_plotG(
        cases_dataframe, 
        ["nb_cases"], 
        "ccaa_name", 
        ["ccaa_name", "nb_cases", "Date"], 
        ["Autonomous communities", "New cases", "Date"],
        "New cases by Autonomous communities"
    )

    cases_figure3 = bar_plot(
        cases_dataframe, 
        "ccaa_name", 
        "nb_cases", 
        "nb_cases", 
        ["nb_cases", "ccaa_name"], 
        ["Total cases", "Autonomous community"], 
        "Total cases by Autonomous communities"
    )

    mortality_figure1 = standard_plotG(
        cases_dataframe, 
        ["defunciones_observadas"], 
        "ccaa_name", 
        ["ccaa_name", "defunciones_observadas", "Date"], 
        ["<b>Autonomous communities</b>", "<i>Mortality</i>", "<i>Date</i>"],
        "Mortality by Autonomous communities"
    )

    mortality_figure2 = standard_plot(
        cases_dataframe, 
        "defunciones_observadas", 
        ["defunciones_observadas", "Date"], 
        ["Mortality", "Date"],
    )

    other_figure = standard_plot(
        cases_dataframe, 
        ["num_hosp", "num_uci"], 
        ["variable", "value", "Date"], 
        ["Indicator", "Value", "Date"],
    )
    other_figure = custom_legend_name(other_figure, ['Healed','Intensive care'], ['#151515', '#E4E4E2'])

    return render_template(
        'index.html',  
        graphJSON_vaccines_all=generate_figureJSON(vaccines_figure1), 
        graphJSON_vaccines_ccaa=generate_figureJSON(vaccines_figure2),
        graphJSON_cases_all=generate_figureJSON(cases_figure1),
        graphJSON_cases_ccaa=generate_figureJSON(cases_figure2),
        graphJSON_cases_bar=generate_figureJSON(cases_figure3) ,
        graphJSON_deaths_all=generate_figureJSON(mortality_figure1),
        graphJSON_deaths_ccaa=generate_figureJSON(mortality_figure2),
        graphJSON_other=generate_figureJSON(other_figure),
        info=stats(cases_dataframe, vaccines),
        map=generate_figureJSON(choropleth_map(cases_dataframe)), 
    )


@app.route('/forecast')
def forecast():
    return render_template(
        'forecast.html', 
        forecast_json = generate_figureJSON(forecasting(cases_dataframe)["figure"]), 
        forecast_info = forecasting(cases_dataframe)["info"], 
        last_date = forecasting(cases_dataframe)["last_update"]
        )

@app.route('/data')
def data():
	return render_template('data.html')

@app.route('/data/covid_cases')
def download_data_c():
    table_name = "covid_cases"
    cols = ["Date", "ccaa_iso", "nb_cases", "num_hosp", "num_uci", "defunciones_observadas"]
    return download_data(table_name, cols)

@app.route('/data/vaccines')

def download_data_v():
    table_name = "vaccins"
    cols = ["`Date`", "`community`", "`Total doses delivered`", "`Doses administered`", "`No. People vaccinated`", "`ccaa_iso`"]
    return download_data(table_name, cols)

def stats(data1, data2) : 

    data1 = data1.set_index('Date')
    data2 = data2.set_index('Date')

    grouped_data1 = data1.groupby(data1.index).sum()
    grouped_data2 = data2.groupby(data2.index).sum()

    data1_ld = grouped_data1.index.to_list()[-1]
    data2_ld = grouped_data2.index.to_list()[-1]

    totals = grouped_data1.sum()
    total_cases, total_deaths = totals["nb_cases"], totals["defunciones_observadas"]
    total_vaccines = grouped_data2.iloc[-1]["No. People vaccinated"]
    percentage = (grouped_data2.loc[data2_ld]["No. People vaccinated"]/47450795)
    print("------------------------------------------------total cases", total_cases)

    info = {
        "data1_ld" :  data1_ld, 
        "data2_ld" :  data2_ld, 
        "new_cases" : grouped_data1.loc[data1_ld]["nb_cases"],
        "new_deaths" : grouped_data1.loc[data1_ld]["defunciones_observadas"],
        "new_hosp" : grouped_data1.loc[data1_ld]["num_hosp"], 
        "new_uci" : grouped_data1.loc[data1_ld]["num_uci"], 
        "total_delivered" : millify(grouped_data2.loc[data2_ld]["Total doses delivered"]), 
        "percentage" : "{:.2f} %".format(percentage*100),
        "total_vaccines" : '{:,}'.format(total_vaccines).replace(',', ' '), 
        "total_cases" : '{:,}'.format(total_cases).replace(',', ' '), 
        "total_deaths" : '{:,}'.format(total_deaths).replace(',', ' ')
    }
    return info

if __name__ == '__main__':
    app.run(debug=True)