FROM l4t:latest

# Definition of a Device & Service
ENV POSITION=Runtime \
    SERVICE=get-plc-backup-omron-with-ftp \
    AION_HOME=/var/lib/aion \
    MYSQL_SERVICE_HOST=mysql \
    MYSQL_USER=latona \
    MYSQL_PASSWORD=latonalatona

RUN mkdir ${AION_HOME}
WORKDIR ${AION_HOME}
# Setup Directoties
RUN mkdir -p \
    $POSITION/$SERVICE
WORKDIR ${AION_HOME}/$POSITION/$SERVICE/
ADD . .
RUN pip3 install simplejson
RUN python3 setup.py install
CMD ["python3", "-m", "get_plc_omron_backup"]
