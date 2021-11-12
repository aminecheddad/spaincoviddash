from airflow import DAG
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.python_operator import PythonOperator
import datetime
import airflow
import time
import requests

def download_file(attempts = 3) : 
    #preparing the file url
    current_date = datetime.date.today().strftime("%Y%m%d")
    full_link = "https://www.mscbs.gob.es/profesionales/saludPublica/ccayes/alertasActual/nCov/documentos/Informe_Comunicacion_{}.ods".format(current_date)
    
    #downloading file  
    try:
        rq = requests.get(full_link)
        rq.raise_for_status()
        print("File at {} downloaded successfully".format(full_link))
        with open("/home/kali/COVID-19-ES/airflow/download_file/downloads/Informe_Comunicacion_{}.ods".format(current_date), "wb") as file :
            file.write(rq.content)
        return True
    except requests.exceptions.HTTPError as err:
        if attempts > 0 : 
            print("Error while downloading {link} remaining attempt {attempt_count}".format(
                link = full_link, 
                attempt_count = attempts
            ))
            time.sleep(3600) #wait for 1h and try again
            download_file(attempts-1)
            
        with open("/home/kali/COVID-19-ES/airflow/download_file/downloads/logs/log_{date}.txt".format(date = current_date), "w") as file : 
            file.write(str(err))
        return False

default_args = {
    "depends_on_past" : False,
    "start_date"      : airflow.utils.dates.days_ago( 1 ),
    "retries"         : 1,
    "retry_delay"     : datetime.timedelta( hours= 5 ),
}

with DAG('download_worksheet',  default_args= default_args, schedule_interval='30 23 * * *') as dag:
    python_task	= PythonOperator(task_id='python_task', python_callable=download_file)