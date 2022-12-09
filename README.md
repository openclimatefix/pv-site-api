# PVSiteAPI
Site specific API for SBRI project


# docker tests
```
docker stop $(docker ps -a -q)
docker-compose -f infrastructure/test-docker-compose.yml build
docker-compose -f infrastructure/test-docker-compose.yml run api
```