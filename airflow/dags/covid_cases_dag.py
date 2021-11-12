import requests
import time
import datetime
import pandas as pd
import io
from sqlalchemy import exc
import sqlalchemy
from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
import airflow

provincias_data = {
    "C":"GA",
    "VI":"PV",
    "AB":"CM",
    "A":"VC",
    "AL":"AN",
    "O":"AS",
    "AV":"CL",
    "BA":"EX",
    "PM":"IB",
    "B":"CT",
    "BI":"PV",
    "BU":"CL",
    "CC":"EX",
    "CA":"AN",
    "S":"CB",
    "CS":"VC",
    "CR":"CM",
    "CO":"AN",
    "CU":"CM",
    "SS":"PV",
    "GI":"CT",
    "GR":"AN",
    "GU":"CM",
    "H":"AN",
    "HU":"AR",
    "J":"AN",
    "LO":"RI",
    "GC":"CN",
    "LE":"CL",
    "L":"CT",
    "LU":"GA",
    "M":"MD",
    "MA":"AN",
    "MU":"MC",
    "NA":"NC",
    "OR":"GA",
    "P":"CL",
    "PO":"GA",
    "SA":"CL",
    "TF":"CN",
    "SG":"CL",
    "SE":"AN",
    "SO":"CL",
    "T":"CT",
    "TE":"AR",
    "TO":"CM",
    "V":"VC",
    "VA":"CL",
    "ZA":"CL",
    "Z":"AR",
    "CE":"CE", 
    "ML": "ML", 
    "nan":"nan"
}


def _apply(key) : 
    try : 
        x = provincias_data[key]
        return x
    except :
        pass

def download_file(attempts = 3) : 
    #preparing the file url
    full_link = "https://cnecovid.isciii.es/covid19/resources/casos_hosp_uci_def_sexo_edad_provres.csv"
    
    #downloading file  
    try:
        rq = requests.get(full_link)
        rq.raise_for_status()
        print("File at {} downloaded successfully".format(full_link))
        dataframe = pd.read_csv(io.StringIO(rq.content.decode('utf-8')))
        return dataframe
    except requests.exceptions.HTTPError as err:
        if attempts > 0 : 
            print("Error while downloading {link} remaining attempt {attempt_count}".format(
                link = full_link, 
                attempt_count = attempts
            ))
            time.sleep(5400) #wait for 1h 30min and try again
            download_file(attempts-1)
            
        with open("covid_cases/logs/log_{date}.txt".format(date = current_date), "w") as file : 
            file.write(str(err))
        return False
        
def c_engine(host, username, pwd, db_name, attempts = 3) :
    try : 
        engine = sqlalchemy.create_engine('mysql+mysqlconnector://{user}:{password}@{host}/{database}'.format(
            user = username,
            password = pwd, 
            host = host,
            database = db_name))
        return engine
    
    except exc.SQLAlchemyError as error:
        if attempts>0:
            print("An error has occured ", error)
            time.sleep(30)
            c_engine(host, username, pwd, db_name, attempts-1)
    return False


# creating engine 

engine = c_engine("", "", "", "")


def check_state(engine) : 
    try:
        sql_query = pd.read_sql_query(
            '''SELECT * FROM covid_cases''', engine)
        dataframe = pd.DataFrame(sql_query)
        if dataframe.empty : 
            return False, None
        else : 
            return True, dataframe
    except exc.SQLAlchemyError as error:
        print("An error has occured", error)
        return False, None
    
def get_diffence(dataframe1, dataframe2):
    diff = pd.concat([dataframe1,dataframe2]).drop_duplicates(keep=False)
    return diff

def insert(engine, dataframe, attempts = 3): 
    try :
        dataframe.to_sql(con=engine, name='covid_cases', if_exists='append')
        print("Successful")
    except : 
        if attempts>0 : 
            print("An error has occured")
            time.sleep(30)
            insert(engine, dataframe, attempts-1)

def perform_modifications(dataframe) :
    #add autonomous columns 
    dataframe["ccaa_iso"] =  dataframe["provincia_iso"].apply(lambda x: _apply(x))
    df = dataframe.groupby(["fecha", "ccaa_iso"], as_index = False).sum()

    #rename columns 
    df.columns = ["Date", "ccaa_iso", "nb_cases", "num_hosp", "num_uci", "defunciones_observadas"]
    return df

def insert_into(**kwargs) : 
    #add a new column for autonomous communities
    new_dataframe = download_file()

    engine = kwargs['engine']
    #checking state !
    state, old_dataframe = check_state(engine)
    if state : 
        diff = get_diffence(perform_modifications(new_dataframe), old_dataframe[["Date", "ccaa_iso", "nb_cases", "num_hosp", "num_uci", "defunciones_observadas"]])
        insert(engine, diff)
    else:
        insert(engine, perform_modifications(new_dataframe))

default_args = {
    "depends_on_past": False,
    "start_date": airflow.utils.dates.days_ago(1),
    "retries": 1, 
    "retry_delay": datetime.timedelta(hours=5)
}

with DAG('covid_cases_dag', default_args = default_args, schedule_interval='@once') as dag : 
    python_task = PythonOperator(task_id = 'python_task', python_callable= insert_into, op_kwargs = {'engine': engine})
