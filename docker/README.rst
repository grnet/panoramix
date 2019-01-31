Build image
-----------
1. Initialize code to be included in the image. We don't include 
   the root repo dir to prevent image rebuilds for every minor 
   change in current repo.

      $ ./docker/init-repos.sh
      $ docker build -t consensus .

Create container
----------------

- Demo container

  $ docker run -e NRTRUSTEES=<nr trustees> -p <localport>:9000 -ti consensus


- Development container, mounts app and ui local dirs to docker container

  $ docker create --name consensus-dev \
     -p 9000:9000 \
     -e NRTRUSTEES=2 \
     -v ${PWD}:/srv/app \
     -v ${PWD}/ui:/srv/ui \
     consensus;

