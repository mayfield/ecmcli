FROM ecmcli-platform
RUN python ./setup.py -q install
ENTRYPOINT ecm
