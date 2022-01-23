# Projet spaincoviddash 

Le virus COVID-19 était connu du monde fin 2019 et après plus de 10 mois d'efforts mondiaux, des traitements réussis du virus à l'aide de certains vaccins n'ont pas été obtenus. Le SARS-CoV-2, le virus responsable de la crise du COVID-19, est en constante évolution et comprendre les tendances de son évolution est fondamental pour contrôler la pandémie. 
Notre objectif dans ce travail est d'aider les communautés de HP travaillant en tant que chercheurs, scientifiques et analystes, en fournissant des visualisations et des prédictions. Les données utilisées dans l’application sont de sujets divers : 
<ul>
  <li>Nombre quotidien de nouveaux cas, et décès Covid-19.</li>
  <li>Nombre quotidien des patient COVID-19 guéri et aussi ceux en soins intensifs</li>
  <li>L’évolution de la compagne de vaccination en Espagne. </li>
</ul>
Cette application Web en gros permettra une visualisation emblématique que le monde utilisera pour évaluer la propagation de la pandémie de la maladie à coronavirus 2019 (COVID-19).

# Configuration : 

<h3>Configuration Airflow :</h3>
<ul>
<li>1- Veuillez consulter le tutoriel complet d'installation d'Apache Airflow en visitant le lien suivant <a href = "https://airflow.apache.org/docs/apache-airflow/stable/installation/index.html"><i>https://airflow.apache.org/docs/apache-airflow/stable/installation/index.html</i></a></li>
  <li>2- DAG :</li>
  <ul>
     <li>2-1 : Copiez les dags des fichiers COVID-19-ES/airflow/dags '3 : (covid_cases_dag.py, download_worksheet.py, process_dag.py)</li>
      <li>2-2 : Placez-les dans le répertoire suivant : (airflow/example_dags/)</li>
  </ul>
  <li>3- Lancer le serveur web et le scheduler</li>
</ul>
<h3>Configuration de l'application Flask :</h3>
<ul>
  <li>1- Ouvrez 'COVID-19-ES/flask-app'</li>
  <li>2- Installez les packages par (<i>pip install requirements.txt</i>)</li>
  <li>3- Ouvrez le terminal et tapez (python app.py) puis ouvrez le navigateur à l'adresse IP locale donnée. </li>
</ul>

