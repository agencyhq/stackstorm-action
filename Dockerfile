
FROM python:2-slim

WORKDIR /app

RUN apt-get -y update \
  && apt-get -y install build-essential git \
  && apt-get clean

RUN pip install -e "git+https://github.com/stackstorm/st2.git#egg=st2common&subdirectory=st2common"
RUN pip install -e "git+https://github.com/StackStorm/st2.git#egg=python_runner&subdirectory=contrib/runners/python_runner"

ARG packs

COPY bootstrap.sh /app/

RUN sh bootstrap.sh ${packs}

COPY . /app/

ENTRYPOINT [ "./entrypoint.sh" ]
CMD [ "python", "handler.py" ]
