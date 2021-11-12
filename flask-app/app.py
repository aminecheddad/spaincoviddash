from flask import Flask, render_template, url_for, redirect, request, Response
import pandas as pd
import plotly
import datetime
import plotly.express as px
from urllib.request import urlopen
import json
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
from flaskext.mysql import MySQL


app = Flask(__name__, template_folder= 'template')

mysql = MySQL()
 
# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = "u5487210@cvp19"
app.config['MYSQL_DATABASE_PASSWORD'] = "jRG2XXi4CwjHvAa"
app.config['MYSQL_DATABASE_DB'] = "my_db"
app.config['MYSQL_DATABASE_HOST'] = "cvp19.mysql.database.azure.com"
mysql.init_app(app)

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

#our data
cases_dataframe = get_dataframe('covid_cases')
vaccines = get_dataframe('vaccins')
cases_dataframe["Date"] = pd.to_datetime(cases_dataframe["Date"])
vaccines["Date"] = pd.to_datetime(vaccines["Date"])


@app.route('/data')
def data():
	return render_template('data.html')

@app.route('/data/covid_cases')
def download_data_c():
	conn = None
	cursor = None
	try:
		conn = mysql.connect()
		cursor = conn.cursor(pymysql.cursors.DictCursor)

		cursor.execute("SELECT Date, ccaa_iso, nb_cases, num_hosp, num_uci, defunciones_observadas FROM covid_cases")
		result = cursor.fetchall()
		keys = list(result[0].keys())
		output = io.StringIO()
		writer = csv.DictWriter(output, fieldnames = keys)
		writer.writeheader()
		for row in result:
			writer.writerow(row)

		output.seek(0)
		
		return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=cases_data.csv"})
	except Exception as e:
		print(e)
	finally:
		cursor.close() 
		conn.close()

@app.route('/data/vaccines')
def download_data_v():
	conn = None
	cursor = None
	try:
		conn = mysql.connect()
		cursor = conn.cursor(pymysql.cursors.DictCursor)

		cursor.execute("SELECT `Date`, `community`, `Total doses delivered`, `Doses administered`, `No. People vaccinated`, `ccaa_iso` FROM vaccins")
		result = cursor.fetchall()
		keys = list(result[0].keys())
		output = io.StringIO()
		writer = csv.DictWriter(output, fieldnames = keys)
		writer.writeheader()
		for row in result:
			row['Date'] = row['Date'].strftime("%Y-%m-%d")
			writer.writerow(row)

		output.seek(0)
		
		return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=vaccines_data.csv"})
	except Exception as e:
		print(e)
	finally:
		cursor.close() 
		conn.close()

@app.route('/')
def index():
    return render_template(
        'index.html',  
        graphJSON_vaccines_all=plot_vaccines("all", vaccines)[0], 
        graphJSON_vaccines_ccaa=plot_vaccines("ccaa", vaccines),
        graphJSON_cases_all=plot_cases("all", cases_dataframe)[0],
        graphJSON_cases_ccaa=plot_cases("ccaa", cases_dataframe)[0],
        graphJSON_cases_bar = plot_cases("ccaa", cases_dataframe)[1],
        graphJSON_deaths_all=plot_deaths("all", cases_dataframe)[0],
        graphJSON_deaths_ccaa=plot_deaths("ccaa", cases_dataframe),
        graphJSON_hosp=plot_hosp(cases_dataframe)[0],
        updated_stats=stats(cases_dataframe, vaccines),
        map=choropleth_map(cases_dataframe), 
        cases_info = plot_cases("all", cases_dataframe)[1], 
        deaths_info = plot_deaths("all", cases_dataframe)[1], 
        vaccines_info = plot_vaccines("all", vaccines)[1], 
        hosp_info = plot_hosp(cases_dataframe)[1]
    )

@app.route('/forecast')
def forecast():
    return render_template('forecast.html', forecast_json = plot_forecast(cases_dataframe)[0], forecast_info = plot_forecast(cases_dataframe)[1], last_date = plot_forecast(cases_dataframe)[2])

def plot_forecast(data) : 

    #import original data
    data = data.groupby("Date", as_index = False).sum()[["Date", "nb_cases"]].iloc[55:]

    data["Date"] = pd.to_datetime(data["Date"])
    data.columns = ['ds', 'y']
    last_date = data.iloc[-1]["ds"]

    #load model 
    with open('models/prophet_v2.pckl', 'rb') as fin:
        model = pickle.load(fin)

    #making forecast
    future = model.make_future_dataframe(periods=14)
    forecast = model.predict(future)
    forecast[['yhat','yhat_upper','yhat_lower']] = forecast[['yhat','yhat_upper','yhat_lower']].apply(lambda x: inv_boxcox(x, 0.26807530199503693))

    #data card
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
    dt = [lower_band, upper_band, trace1, tracex]
    layout = dict(
        title='New COVID-19 in Spain Prediction Using FbProphet',
        xaxis=dict(title = 'Dates', ticklen=2, zeroline=True), 
        template = "simple_white", 
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    figure=dict(
        data=dt,
        layout=layout
    )
    
    return [json.dumps(figure, cls=plotly.utils.PlotlyJSONEncoder), data_info, last_date]

def plot_vaccines(key, data):
    vaccines_data = data.set_index("Date")
    keys_palette_vaccines_data_plot = set(vaccines_data["community"].to_list())
    palette_vaccines_data_plot_dict = dict(zip(keys_palette_vaccines_data_plot, colors[:len(keys_palette_vaccines_data_plot)]))
    fig2 = px.line(
        vaccines_data, 
        x=vaccines_data.index, 
        y="No. People vaccinated", 
        template="simple_white",
        title = "<b>Vaccines by Autonomous communities</b>", 
        color = "community",
        color_discrete_sequence=px.colors.qualitative.Alphabet,
        color_discrete_map=palette_vaccines_data_plot_dict,
        labels={
                "No. People vaccinated": "<i>Vaccines</i>",
                "index": "<i>Date</i>", 
                "community" : "<b>Autonomous communities</b>"
            }
        )
    fig2.update_traces(textposition="bottom right")
    fig2.update_xaxes(
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
    fig2.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    grouped_vaccines = vaccines_data.groupby(vaccines_data.index).sum()
    fig1 = px.line(
        grouped_vaccines, 
        x=grouped_vaccines.index, 
        y=["No. People vaccinated", "Doses administered", "Total doses delivered"], 
        template="simple_white",
        title = "<b>Vaccines in Spain (Global)</b>",
        labels={
                "x": "<i>Date</i>", 
                "variable" : "<b>Available indicators</b>", 
                "value" : "<i>Vaccines</i>"
            }
        )
    fig1.update_traces(textposition="bottom right")
    fig1.update_xaxes(
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
    fig1.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    for i in range(len(fig1['data'])) : 
        print(fig1['data'][i]["legendgroup"])
        fig1['data'][i]['line']['color']=colors[(i*3)]

    graphJSON = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
    graphJSON_ccaa = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)

    last_date = grouped_vaccines.index.to_list()[-1]
    day_before = (last_date - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    percentage = (grouped_vaccines.loc[last_date]["No. People vaccinated"]/47450795)
    vaccines_inf = {
        "total_delivered" : millify(grouped_vaccines.loc[last_date]["Total doses delivered"]), 
        "last_update" :  last_date, 
        "percentage" : "{:.2f} %".format(percentage*100)
    }

    if key == "ccaa" : 
        return graphJSON_ccaa

    return [graphJSON, vaccines_inf]

def plot_cases(key, data) : 
    data = data.set_index('Date')
    data["ccaa_name"] = data["ccaa_iso"].apply(lambda x : ccaa_names[x])
    #gouvernement decisions 
    gov_df =  pd.read_csv("gov_m.csv")
    gov_df = gov_df.set_index("Date")
    keys_palette_cases_plot = set(data["ccaa_name"].to_list())
    palette_cases_plot_dict = dict(zip(keys_palette_cases_plot, colors[:len(keys_palette_cases_plot)]))
    fig2 = px.line(
        data, 
        x=data.index, 
        y="nb_cases", 
        color="ccaa_name",
        color_discrete_sequence=px.colors.qualitative.Alphabet,
        color_discrete_map=palette_cases_plot_dict,
        template="simple_white",
        title = "<b>New cases by Autonomous communities</b>", 
        labels={
                "ccaa_name": "<b>Autonomous communities</b>",
                "nb_cases": "<i>New cases</i>",
                "Date": "<i>Date</i>"
            }
        )

    fig2.update_traces(textposition="bottom right")
    fig2.update_xaxes(
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

    fig3 = px.bar(
        data.groupby("ccaa_name", as_index = False).sum(), 
        y='nb_cases', 
        x='ccaa_name', 
        text='nb_cases',
        template="simple_white", 
        title = "<b>Total cases by Autonomous communities</b>", 
        color='ccaa_name',
        labels={
                "nb_cases": "<i>Total cases</i>",
                "ccaa_name": "<i>Autonomous community</i>"
            }, 
        color_discrete_map=palette_cases_plot_dict
        )

    fig3.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig3.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
    fig3.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )

    grouped_cases = data.groupby(data.index).sum()
    fig1 = px.line(
        grouped_cases, 
        x=grouped_cases.index, 
        y="nb_cases", 
        template="simple_white",
        labels={
                "nb_cases": "<i>New cases</i>",
                "Date": "<i>Date</i>"
            }
        )
    for date_g in gov_df.to_dict()["mesure"] : 
        fig1.add_vline(
            x=datetime.datetime.strptime(date_g, "%Y-%m-%d").timestamp()*1000, 
            line_width=2, 
            line_dash="dash", 
            line_color="#151515", 
            annotation_text = gov_df.to_dict()["mesure"][date_g]
        )
    fig1.update_layout(annotations=[{**a, **{"y":.5,"yanchor":"bottom","textangle":-90}}  for a in fig1.to_dict()["layout"]["annotations"]])
    fig1.update_traces(textposition="bottom right")
    fig1.update_xaxes(
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
    fig1.update_traces(line_color='#151515')
    fig1.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    fig2.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    graphJSON = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
    graphJSON_ccaa = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
    graphJSON_bar= json.dumps(fig3, cls=plotly.utils.PlotlyJSONEncoder)

    if key == "ccaa" : 
        return [graphJSON_ccaa, graphJSON_bar]

    last_date = grouped_cases.index.to_list()[-1]
    day_before = (last_date- datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    cases_inf = {
        "new_cases" : grouped_cases.loc[last_date]["nb_cases"], 
        "last_update" :  last_date
    }
    return [graphJSON, cases_inf]


def plot_hosp(data) : 

    def custom_legend_name(figure, new_names, c):
        for i in range(len(new_names)):
            figure.data[i].name = new_names[i]
            figure.data[i].line.color = c[i]
    
    data = data.set_index('Date')
    grouped_hosp = data.groupby(data.index).sum()
    fig1 = px.line(
        grouped_hosp, 
        x=grouped_hosp.index, 
        y=["num_hosp", "num_uci"], 
        template="simple_white",
        labels={
                "variable" : "Indicator",
                "value" : "Value",
                "Date": "<i>Date</i>"
            }
        )
    custom_legend_name(fig1, ['Recovered','Intensive care'], ['#151515', '#E4E4E2'])
    fig1.update_traces(textposition="bottom right")
    fig1.update_xaxes(
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
    fig1.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    graphJSON = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)

    last_date = grouped_hosp.index.to_list()[-1]
    hosp_info = {
        "new_hosp" : grouped_hosp.loc[last_date]["num_hosp"], 
        "new_uci" : grouped_hosp.loc[last_date]["num_uci"], 
        "last_update" :  last_date, 
    }
    return [graphJSON, hosp_info]

def plot_deaths(key, data) : 
    data = data.set_index("Date")
    data["ccaa_name"] = data["ccaa_iso"].apply(lambda x : ccaa_names[x])
    keys_palette_deaths_plot = set(data["ccaa_name"].to_list())
    palette_deaths_plot_dict = dict(zip(keys_palette_deaths_plot, colors[:len(keys_palette_deaths_plot)]))
    fig2 = px.line(data, 
                x=data.index, 
                y="defunciones_observadas", 
                color="ccaa_name",
                color_discrete_sequence=px.colors.qualitative.Alphabet,
                color_discrete_map=palette_deaths_plot_dict,
                template="simple_white",
                title = "Mortality by Autonomous communities", 
                labels = {
                        "ccaa_name": "<b>Autonomous communities</b>",
                        "defunciones_observadas": "<i>Mortality</i>",
                        "Date": "<i>Date</i>"
                    }
                )
    fig2.update_traces(textposition="bottom right")
    fig2.update_xaxes(
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
    fig2.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    grouped_deaths = data.groupby(data.index).sum()
    fig1 = px.line(grouped_deaths, 
                x=grouped_deaths.index, 
                y="defunciones_observadas", 
                template="simple_white",
                labels={
                        "defunciones_observadas": "<i>New deaths recoreded</i>",
                        "Date": "<i>Date</i>"
                    }
                )
    fig1.update_traces(textposition="bottom right")
    fig1.update_xaxes(
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
    fig1.update_traces(line_color='#151515')
    fig1.update_layout(
        font=dict(
            family="'Zen Old Mincho', serif",
            color=colors[1]
        )
    )
    graphJSON = json.dumps(fig1, cls=plotly.utils.PlotlyJSONEncoder)
    graphJSON_ccaa = json.dumps(fig2, cls=plotly.utils.PlotlyJSONEncoder)
    if key == "ccaa" : 
        return graphJSON_ccaa
    
    last_date = grouped_deaths.index.to_list()[-1]
    deaths_inf = {
        "new_deaths" : grouped_deaths.loc[last_date]["defunciones_observadas"], 
        "last_update" :  last_date, 
    }
    return [graphJSON, deaths_inf]


def choropleth_map(data) : 

    full_dataframe = data[["Date", "nb_cases", "ccaa_iso"]]
    full_dataframe["ccaa_name"] = full_dataframe["ccaa_iso"].apply(lambda x : ccaa_names[x])
    #select the last date in dataframe
    full_dataframe["Date"].values[-1]
    _14_days_b = full_dataframe["Date"].to_list()[-1]-datetime.timedelta(days = 14)
    full_dataframe = full_dataframe.set_index('Date')
    full_dataframe = full_dataframe.loc[_14_days_b.strftime("%Y-%m-%d"):].groupby("ccaa_name", as_index = False).sum()

    with urlopen('https://raw.githubusercontent.com/codeforgermany/click_that_hood/main/public/data/spain-communities.geojson') as response:
        states = json.load(response)

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
    graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return graphJSON

def stats(data1, data2) : 

    totals = data1[["nb_cases", "defunciones_observadas"]].sum()
    total_cases, total_deaths = totals["nb_cases"], totals["defunciones_observadas"]
    g_vaccunas = data2.set_index('Date')
    total_vaccines = g_vaccunas.groupby(g_vaccunas.index).sum().iloc[-1]["No. People vaccinated"]
    info = {
        "total_cases" : '{:,}'.format(total_cases).replace(',', ' '), 
        "total_deaths" : '{:,}'.format(total_deaths).replace(',', ' '), 
        "total_vaccines" : '{:,}'.format(total_vaccines).replace(',', ' '), 
    }
    return info

if __name__ == '__main__':
    app.run(debug=True)