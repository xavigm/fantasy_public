docker stop fantasy
docker rm fantasy
git pull
docker build . -t fantasy
docker run -d -p 80:5000 --restart unless-stopped --name fantasy -v /opt/fantasy/static:/usr/src/app/static fantasy
