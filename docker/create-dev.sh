docker build -t consensus . || exit;
docker stop consensus-dev; 
docker rm consensus-dev;
docker create --name consensus-dev \
  -p 9000:9000 \
  -v ${PWD}:/srv/app \
  -v ${PWD}/ui:/srv/ui \
  -v ${PWD}/docker/services.conf:/srv/services.conf \
  consensus;
docker start consensus-dev;
