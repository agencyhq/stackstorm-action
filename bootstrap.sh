#!/bin/sh

for pack in $@
do
  git clone https://github.com/StackStorm-Exchange/${pack}/ packs/${pack}
  export PYTHONPATH=$PYTHONPATH:/app/virtualenvs/${pack}/lib/python2.7/site-packages
  mkdir -p /app/virtualenvs/${pack}/lib/python2.7/site-packages
  pip --isolated install --ignore-installed -r /app/packs/${pack}/requirements.txt \
    --prefix /app/virtualenvs/${pack} --src /app/virtualenvs/${pack}/src
done

echo "PYTHONPATH=$PYTHONPATH" >> .env
