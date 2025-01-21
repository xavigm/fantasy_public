![alt text](project_images/AFL_LOGO.png "Title")
# This is Amateur Fantasy League
**Create your own fantasy league for your football, basketball or any other team sport. Upload player cards, register users and much more.**


AFL: Amateur Fantasy League is an app for amateur teams and leagues. In them, they will be able to choose 6 players each day and add their scores to try to lead the classification. They will be able to follow the statistics of each player and the league.

This web application, developed in Python with the Flask Framework, HTML and CSS, has an administrator section to add matchdays, players and weekly scores.
Users can register using a code.
All of this is stored in a MySQL database.

<img src="project_images/1.jpeg" width=20%> <img src="project_images/2.jpeg" width=20%> <img src="project_images/3.jpeg" width=20%> <img src="project_images/4.jpeg" width=20%>

# Getting started
Download the repository and modify the main.py file, adding the data for the MYSQL database, user, password, host and database name. You can import the sql file with sample data that already creates the necessary structure.
Then, you can run the run.sh script to generate the image from the Dockerfile and start the container.
A volume will be mounted in the /opt/fantasy/static directory, and in the photos directory you can upload the images of the players.
With the administrator user (it must have admin boolean active in the database) you can access the administrator panel: menu > administrator.
From there you can create players, putting their name and the name of the image that will be searched for in the previous directory.
You can also create each matchday, and assign the scores of the matchdays of the created players, once they are finished. All from the same panel.
You can also register users, or have them do it themselves through the login page, putting the code that is configured in the main.py file.

# Game
Each user will be able to select 6 players until 23:59h of the day before the matchday. These players will be selected, and once the scores are entered, they will appear in the history, and their points will have been added to the ranking.
You can also see the points in the history by matchday.

# Coming soon
I'm working on v2.0 of AFL, so that player cards are created automatically, and different teams can be managed from the same application. Stay tuned!
